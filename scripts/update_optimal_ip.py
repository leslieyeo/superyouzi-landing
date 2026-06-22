#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动优选「对中国大陆最快的 Cloudflare 入口 IP」，并刷新域名的 A 记录。

原理
----
Cloudflare 免费、不需要 ICP 备案，但它默认分配给免费套餐的 anycast IP
从国内访问经常被污染 / 绕路，慢得像「减速器」。Cloudflare 的边缘是
anycast + 按 SNI/Host 路由的——也就是说，只要把你的域名解析到「一个对
国内更快的 Cloudflare 边缘 IP」，CF 边缘照样会按 Host 头把你的站点内容
吐回来。这就是社区常说的「优选 IP」。

注意：本脚本跑在 GitHub Actions（境外 runner）上，自己测速没有意义
（测出来的是对 runner 最快，不是对国内最快）。所以这里直接拉取由国内
网友实测维护的公开优选 IP 榜单，再把结果写进 DNS。

用法
----
按「存在哪些环境变量」自动选择 DNS 服务商，两者都配则两者都更新：

  Cloudflare:
    CF_API_TOKEN   —— 具备该 Zone 「DNS 编辑」权限的 API Token
    CF_ZONE_ID     —— 域名所在 Zone 的 ID
    CF_DNS_NAME    —— 要维护的完整主机名，如 www.example.com

  DNSPod:
    DNSPOD_TOKEN     —— 形如 "ID,KEY"（DNSPod 的 API Token）
    DNSPOD_DOMAIN    —— 主域名，如 example.com
    DNSPOD_SUBDOMAIN —— 子域名，如 www（根域填 @）

可选：
    IP_COUNT       —— 写入几条 A 记录做轮询，默认 1

未配置任何服务商时直接跳过（退出码 0），方便你先把 workflow 合并、回头再填密钥。
"""

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

# 国内网友实测维护的优选 IP 公开接口，按顺序尝试，取第一个能用的。
# 这些接口格式不一，统一用正则把 IPv4 抠出来，对格式变化更稳。
OPTIMAL_IP_SOURCES = [
    "https://ip.164746.xyz/ipTop.html",
    "https://addressesapi.090227.xyz/CloudFlareYes",
    "https://api.uouin.com/cloudflare.html",
    "https://www.wetest.vip/api/cf2dns/get_cloudflare_ip",
]

IPV4_RE = re.compile(r"(?:\d{1,3}\.){3}\d{1,3}")
TIMEOUT = 20
UA = "Mozilla/5.0 (optimal-ip-bot; +github-actions)"


def http(url, method="GET", headers=None, body=None):
    """发起 HTTP 请求，返回 (status_code, text)。"""
    data = None
    if body is not None:
        data = body if isinstance(body, bytes) else body.encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def is_public_ipv4(ip):
    parts = ip.split(".")
    if len(parts) != 4:
        return False
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return False
    if any(n < 0 or n > 255 for n in nums):
        return False
    # 排除明显的私网 / 保留地址，避免把页面里的杂项数字当 IP
    if nums[0] in (0, 10, 127) or (nums[0] == 192 and nums[1] == 168):
        return False
    if nums[0] == 172 and 16 <= nums[1] <= 31:
        return False
    return True


def fetch_optimal_ips(count):
    for src in OPTIMAL_IP_SOURCES:
        try:
            status, text = http(src, headers={"User-Agent": UA})
        except Exception as e:  # noqa: BLE001 — 网络异常就换下一个源
            print(f"  - 优选源失败 {src}: {e}")
            continue
        if status != 200:
            print(f"  - 优选源 {src} 返回 {status}，跳过")
            continue
        ips = []
        for m in IPV4_RE.findall(text):
            if is_public_ipv4(m) and m not in ips:
                ips.append(m)
            if len(ips) >= count:
                break
        if ips:
            print(f"  - 优选源 {src} 取得 IP: {', '.join(ips)}")
            return ips
    return []


# --------------------------- Cloudflare ---------------------------

def cf_update(token, zone_id, name, ips):
    base = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    hdr = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    status, text = http(f"{base}?type=A&name={urllib.parse.quote(name)}&per_page=100", headers=hdr)
    payload = json.loads(text)
    if not payload.get("success"):
        raise RuntimeError(f"Cloudflare 列记录失败: {text}")
    existing = payload.get("result", [])

    # proxied=False（灰云 / 仅 DNS）是优选 IP 生效的前提：必须让 CF 返回我们
    # 指定的 IP，而不是它自己分配的 anycast IP。
    def record_body(ip):
        return json.dumps({"type": "A", "name": name, "content": ip, "ttl": 60, "proxied": False})

    for i, ip in enumerate(ips):
        if i < len(existing):
            rid = existing[i]["id"]
            st, tx = http(f"{base}/{rid}", method="PUT", headers=hdr, body=record_body(ip))
        else:
            st, tx = http(base, method="POST", headers=hdr, body=record_body(ip))
        if not json.loads(tx).get("success"):
            raise RuntimeError(f"Cloudflare 写入 {name} -> {ip} 失败: {tx}")
        print(f"  - Cloudflare {name} -> {ip}")

    # 多出来的旧记录删掉，保持记录数 == len(ips)
    for rec in existing[len(ips):]:
        http(f"{base}/{rec['id']}", method="DELETE", headers=hdr)
        print(f"  - Cloudflare 删除多余记录 {rec['content']}")


# ----------------------------- DNSPod -----------------------------

def dnspod_call(action, params):
    url = f"https://dnsapi.cn/{action}"
    body = urllib.parse.urlencode(params)
    hdr = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "optimal-ip-bot/1.0 (github actions)",
    }
    status, text = http(url, method="POST", headers=hdr, body=body)
    data = json.loads(text)
    return data


def dnspod_update(token, domain, sub_domain, ips):
    common = {"login_token": token, "format": "json"}

    listed = dnspod_call("Record.List", dict(common, domain=domain, sub_domain=sub_domain, record_type="A"))
    code = listed.get("status", {}).get("code")
    # 3000 = 子域名下暂无记录，视为空列表
    existing = listed.get("records", []) if code == "1" else []

    for i, ip in enumerate(ips):
        if i < len(existing):
            dnspod_call("Record.Modify", dict(
                common, domain=domain, record_id=existing[i]["id"], sub_domain=sub_domain,
                record_type="A", record_line_id="0", value=ip, ttl="60"))
        else:
            dnspod_call("Record.Create", dict(
                common, domain=domain, sub_domain=sub_domain,
                record_type="A", record_line_id="0", value=ip, ttl="60"))
        print(f"  - DNSPod {sub_domain}.{domain} -> {ip}")

    for rec in existing[len(ips):]:
        dnspod_call("Record.Remove", dict(common, domain=domain, record_id=rec["id"]))
        print(f"  - DNSPod 删除多余记录 {rec.get('value')}")


# ------------------------------ main ------------------------------

def main():
    count = max(1, int(os.environ.get("IP_COUNT") or "1"))

    cf = all(os.environ.get(k) for k in ("CF_API_TOKEN", "CF_ZONE_ID", "CF_DNS_NAME"))
    dp = all(os.environ.get(k) for k in ("DNSPOD_TOKEN", "DNSPOD_DOMAIN", "DNSPOD_SUBDOMAIN"))

    if not (cf or dp):
        print("未配置任何 DNS 服务商（Cloudflare / DNSPod），跳过。")
        print("配置方法见 README「国内访问优化」一节。")
        return 0

    print("拉取国内优选 Cloudflare IP …")
    ips = fetch_optimal_ips(count)
    if not ips:
        # 优选源是外部第三方服务，偶发不可达属正常。这种情况只跳过本轮、
        # 不动 DNS，也不让 workflow 报红（避免定时任务反复发失败通知）。
        # 真正的配置/接口错误会在下面写 DNS 时抛出，照常报错。
        print("优选 IP 源暂不可达，本轮跳过（不改 DNS）。")
        return 0

    if cf:
        print("更新 Cloudflare DNS …")
        cf_update(os.environ["CF_API_TOKEN"], os.environ["CF_ZONE_ID"],
                  os.environ["CF_DNS_NAME"], ips)
    if dp:
        print("更新 DNSPod DNS …")
        dnspod_update(os.environ["DNSPOD_TOKEN"], os.environ["DNSPOD_DOMAIN"],
                      os.environ["DNSPOD_SUBDOMAIN"], ips)

    print("完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
