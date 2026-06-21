# superyouzi-landing

超级游资（superyouzi-skills）产品落地页 —— 纯静态前端。

- `index.html`：落地页首页
- `assets/avatars/`：评委/大师头像
- `sales/样报/`：3 份公开样报（HTML + 预览图）

通过 GitHub Pages 托管：https://leslieyeo.github.io/superyouzi-landing/

> 本仓库仅含对外公开的落地页内容，不含任何付费 skill 源码。

---

## 国内访问优化（免备案）

页面本身已无任何境外 CDN 依赖（字体子集化本地打包、头像本地化、首屏图片懒加载）。
要让国内访问更快更稳、又**不走 ICP 备案**，推荐：

> **GitHub Pages 作源站 → 自有域名挂 Cloudflare → 定时「优选 IP」把域名指向对国内最快的 CF 边缘节点。**

本仓库已内置自动「优选 IP」流程，无需服务器：

- `.github/workflows/optimal-ip.yml`：每 30 分钟运行（也可手动触发）
- `scripts/update_optimal_ip.py`：拉取国内网友实测的优选 IP，刷新你的 DNS A 记录（仅标准库，无三方依赖）

### 配置（二选一，按你的 DNS 服务商）

在仓库 **Settings → Secrets and variables → Actions** 里加密钥：

**A. 用 Cloudflare 自带 DNS**

| Secret | 说明 |
|---|---|
| `CF_API_TOKEN` | 具备该 Zone「DNS 编辑」权限的 API Token |
| `CF_ZONE_ID` | 域名所在 Zone 的 ID |
| `CF_DNS_NAME` | 要维护的完整主机名，如 `www.example.com` |

**B. 用 DNSPod（国内线路解析更细）**

| Secret | 说明 |
|---|---|
| `DNSPOD_TOKEN` | 形如 `ID,KEY` |
| `DNSPOD_DOMAIN` | 主域名，如 `example.com` |
| `DNSPOD_SUBDOMAIN` | 子域名，如 `www`（根域填 `@`） |

可选变量（Variables）`IP_COUNT`：写入几条 A 记录做轮询，默认 `1`。

> 两组都填则两边都更新。一个都不填时 workflow 会直接跳过（绿色通过），方便先合并、回头再配。

### 前提与注意

- 域名需先在 Cloudflare 建好 Zone 且站点能正常访问；优选 IP 走 **DNS-only（灰云）** 记录才生效——
  脚本写 Cloudflare 记录时已固定 `proxied=false`。
- 优选 IP 榜单来自第三方公开接口，偶发不可达时脚本只跳过本轮、不动现有解析。
- 域名本身不需要备案，只要不解析到境内服务器即可。
