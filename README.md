# superyouzi-landing

超级游资（superyouzi-skills）产品落地页 —— 纯静态前端。

- `index.html`：落地页首页
- `assets/avatars/`：评委/大师头像
- `sales/样报/`：3 份公开样报（HTML + 预览图）

线上部署在 **Cloudflare Pages**，自有域名（免备案）：https://superyouziskill.store （含 `www`）。
Pages 源域名：https://superyouziskill.pages.dev

> 本仓库仅含对外公开的落地页内容，不含任何付费 skill 源码。

---

## 国内访问优化（免备案）

已落地的优化（全程不走 ICP 备案）：

1. **去外部依赖**：字体子集化本地打包、移除 jsdelivr、头像全部本地化——无任何会被墙的外链。
2. **首屏瘦身**：字体 `preload` + 首屏外图片懒加载（37 头像 + 2 大样报图），首屏请求从 ~4MB 降到 ~0.7MB。
3. **Cloudflare Pages + 自有域名**：站点部署在 Cloudflare Pages，自有域名 `superyouziskill.store`（橙云代理 + 自动 HTTPS），走 Cloudflare 全球边缘 + 缓存，比 GitHub Pages 在国内更快更稳。

### 关于「优选 IP」（当前不启用）

仓库内置了一套优选 IP 自动化（`.github/workflows/optimal-ip.yml` + `scripts/update_optimal_ip.py`，
仅标准库、按 secrets 自动识别 Cloudflare / DNSPod）。

但**注意**：当域名 zone 托管在 Cloudflare 且用 Pages 自定义域时，把记录改成「灰云 A 指向优选 IP」会触发
**Error 1000** 使自定义域失效。因此该流程在**当前架构下不启用**，相关 secrets 也未配置。

它只适用于「访问域 DNS 放在 DNSPod 等非 Cloudflare 服务商」的场景：先 CNAME 到 Pages、等证书签好，
再把记录改成灰云优选。配置说明见 `scripts/update_optimal_ip.py` 顶部注释。
