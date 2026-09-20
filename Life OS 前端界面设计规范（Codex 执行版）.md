---
title: "Life OS 前端界面设计规范（Codex 执行版）"
type: design-source
created: 2026-09-18T15:50:15+08:00
updated: 2026-09-20T09:09:00+08:00
status: draft
related:
  - "[[项目说明]]"
  - "[[前端设计与技术架构提纲]]"
  - "[[M4前端建设记录]]"
---

# Life OS 前端界面设计规范

## 一、产品定位

Life OS 是一个长期使用的个人生活管理与记录系统。

它的首页和核心界面不应被设计成传统企业 Dashboard，也不应只是若干数据卡片的集合。

核心设计理念是：

**帮助用户快速理解「我当前的生活状态是什么」；在此基础上进行记录、回顾、分析和行动。**

前端需要为未来持续扩展预留空间，包括但不限于：

- 今日状态
- 任务与计划
- 习惯
- 健康与运动
- 睡眠
- 财务
- 阅读与学习
- 日记与记录
- 长期目标
- 项目
- 旅行
- AI 总结与分析
- 长期趋势

所有模块应属于同一套统一设计语言，而不是各自独立成不同风格的子系统。

---

# 二、视觉设计总方向

整体视觉风格定义为：

**现代东方极简 / Neo-Chinese Minimalism**

设计目标：

**简洁、优雅、现代、克制，同时具有明确的东方审美特征和适度活力。**

东方感主要通过以下元素建立：

- 配色
- 留白
- 字体层级
- 页面比例
- 信息节奏
- 边界与分隔方式

不要通过大量传统文化装饰元素制造“中国风”。

应避免：

- 祥云
- 卷轴
- 水墨背景
- 古建筑纹样
- 大面积印章元素
- 毛笔字体
- 复杂国风插画
- 红金主视觉
- 过度仿古设计

目标不是“古风网站”，而是：

**一个属于现代中国用户的高级个人数字系统。**

---

# 三、核心配色方向

用户明确偏好：

**青黛、天青、青绿色体系。**

主色体系应具有以下特征：

**东方、沉静、清爽，同时具有适度生命力。**

推荐基础 Design Tokens：

```css
--background: #F7F5EF;
--surface: #FBFAF6;
--surface-muted: #EFEDE6;

--text-primary: #252827;
--text-secondary: #68706D;
--text-muted: #969D99;

--border: #DDDCD5;
--border-strong: #C9CCC7;

--primary: #3F625F;
--primary-hover: #345552;
--primary-light: #DDE9E6;

--cyan: #729B99;
--cyan-light: #D9EAE7;

--jade: #5E8076;
--green-muted: #718B78;

--vermillion: #B95549;
--gold: #A58955;
```

色彩关系建议：

```text
宣纸暖白 / 浅灰         65–75%
墨色 / 灰色            15–20%
青黛 / 天青             8–12%
朱砂 / 赭金 / 其他点缀   2–5%
```

## 配色原则

### 1. 青黛作为核心品牌色

青黛用于：

- 主按钮
- 当前导航状态
- 重点链接
- 图表核心系列
- 选择状态
- Active 状态
- Focus 状态

不要把整个页面染成青色。

### 2. 天青用于提供活力

天青可以用于：

- 图表
- Hover
- Secondary Accent
- 数据趋势
- 浅色背景块
- 状态提示

青黛负责“稳定”，天青负责“空气感和生命力”。

### 3. 朱砂只作为点睛

朱砂不可成为主色。

主要用于：

- 重要提醒
- 异常
- 删除
- 关键标记
- 少量视觉焦点

### 4. 暖白代替纯白

页面背景避免长期使用：

```css
#FFFFFF
```

优先使用略带暖色的宣纸白、米白和浅灰。

这样可以降低工具软件的冰冷感。

---

# 四、页面气质

页面整体应呈现：

**安静，但不沉闷；现代，但不冰冷；东方，但不仿古。**

UI 应更多依靠以下元素构建信息层级：

- 留白
- 字号
- 字重
- 字色
- 细分隔线
- 背景轻微差异

而不是依赖：

- 大量阴影
- 高饱和颜色
- 大面积渐变
- Glassmorphism
- 夸张圆角
- 浮动卡片
- 每个模块都使用独立 Card

---

# 五、首页设计原则

首页不是“数据中心”，而是：

**生活状态首页。**

进入 Life OS 后，应优先回答：

1. 今天是什么状态？
2. 今天有哪些值得关注的事情？
3. 最近一段时间生活发生了什么变化？
4. 有没有值得立即行动或回顾的内容？

首页建议采用类似以下结构：

```text
日期 / 问候
│
├── 今日状态
│
├── 今日重要事项
│
├── 当前生活概览
│   ├── 健康
│   ├── 习惯
│   ├── 财务
│   └── 专注 / 学习
│
├── 最近趋势
│
└── 最近记录
```

不要开屏展示十几个等尺寸 KPI Card。

首页的信息应存在明确主次关系。

---

# 六、布局风格

建议采用：

```text
左侧导航 + 主内容区
```

桌面端结构：

```text
┌───────────┬──────────────────────────────┐
│           │                              │
│ Life OS   │       Main Content           │
│           │                              │
│ 今日      │                              │
│ 记录      │                              │
│ 健康      │                              │
│ 财务      │                              │
│ 学习      │                              │
│ 项目      │                              │
│           │                              │
└───────────┴──────────────────────────────┘
```

Sidebar 保持克制。

不要使用复杂渐变、巨大 Logo 或大量图标装饰。

导航优先使用：

**图标 + 中文名称**

图标统一使用 Lucide。

---

# 七、卡片设计

减少“Card Everywhere”。

只有在内容确实需要形成语义区域时使用 Card。

Card 建议：

```css
border-radius: 8px;
border: 1px solid var(--border);
box-shadow: none;
```

或只使用极轻阴影。

避免：

```css
border-radius: 20px;
box-shadow: 0 10px 40px ...
```

页面应该接近：

**数字书页 / 工作台**

而不是移动 App 卡片流。

---

# 八、圆角规范

整体保持现代但克制。

建议：

```text
Button         6–8px
Input          6–8px
Card           8–10px
Modal          10–12px
Tag            4–6px
```

不要默认使用 16px、20px、24px 大圆角。

避免明显的 AI SaaS 模板感。

---

# 九、字体体系

正文优先采用现代中文无衬线字体：

```text
PingFang SC
Microsoft YaHei
Noto Sans SC
Source Han Sans SC
```

正文、表格、数字、按钮统一使用 Sans Serif。

标题可以在非常有限的位置使用：

```text
Noto Serif SC
Source Han Serif SC
```

例如：

- 首页日期
- 页面大标题
- 月度总结标题
- 日记标题

宋体只承担“东方气质”，不能承担大量 UI 信息。

禁止使用毛笔字体作为 UI 字体。

---

# 十、Typography 层级

建议建立稳定层级，而不是随意改变字号。

例如：

```text
Page Title      28–32px
Section Title   18–20px
Card Title      15–16px
Body            14–15px
Secondary       13px
Caption         12px
```

数字类核心指标可适当放大：

```text
28–40px
```

但避免所有 KPI 都巨大化。

---

# 十一、数据可视化风格

图表统一使用东方青色 Palette。

推荐：

```text
青黛
天青
竹青
松绿
赭金
藕灰
朱砂
```

所有图表必须与整体 UI 共用 Design Tokens。

禁止直接使用图表库默认：

```text
蓝
红
黄
绿
紫
```

图表设计应：

- 减少网格线
- 减少图例干扰
- 强调趋势
- 使用低饱和配色
- Tooltip 简洁
- 坐标轴颜色弱化
- 不使用 3D 图表
- 不使用视觉噪声高的渐变

---

# 十二、交互风格

交互要：

**轻、快、明确。**

Hover：

- 轻微背景变化
- 轻微颜色变化

Active：

- 青黛色
- 或青黛浅背景

动画：

```text
150–250ms
```

推荐：

```css
transition: background-color 180ms ease,
            color 180ms ease,
            border-color 180ms ease;
```

避免：

- 大量弹跳动画
- 元素飞入
- 页面频繁缩放
- 长时间动效
- 炫技型 Motion

---

# 十三、技术栈

前端技术框架固定为：

```text
React
TypeScript
Vite
Tailwind CSS
shadcn/ui
Lucide Icons
React Router
TanStack Query
Apache ECharts
```

职责划分：

```text
React
→ 页面与组件

Tailwind
→ Design Tokens / Layout / Styling

shadcn/ui
→ 基础 UI 组件

Lucide
→ 图标

React Router
→ 模块路由

TanStack Query
→ API Data / Cache / Mutation

ECharts
→ 图表与长期数据趋势
```

---

# 十四、后端交互原则

前端不得直接访问：

```text
Beancount
DuckDB
SQLite
Parquet
Markdown 文件
```

所有业务数据统一通过：

```text
FastAPI
```

访问。

正确架构：

```text
React UI
   ↓
TanStack Query
   ↓
FastAPI
   ↓
Domain Services
   ↓
Beancount / SQLite / DuckDB / Markdown / Parquet
```

前端只理解 API Contract，不理解底层数据实现。

例如：

```text
GET  /api/v1/life/today
GET  /api/v1/life/summary

GET  /api/v1/finance/summary
GET  /api/v1/health/summary

GET  /api/v1/habits
POST /api/v1/habits

GET  /api/v1/journal
POST /api/v1/journal
```

---

# 十五、财务系统边界

不要重新实现 Fava。

Life OS 中财务模块负责：

- 财务摘要
- 本月收支
- 净资产
- 储蓄率
- 分类趋势
- 长期资产变化

专业账本查询继续由：

```text
Beancount + Fava
```

承担。

Life OS 可以提供：

```text
进入财务账本
```

作为跳转入口。

---

# 十六、状态管理原则

优先使用：

```text
TanStack Query
```

管理后端数据。

不要为了简单状态引入 Redux。

组件内部 UI 状态：

```text
useState
```

即可。

只有确实出现复杂的跨组件客户端状态后，再考虑 Zustand 等额外方案。

不得提前增加不必要的状态管理复杂度。

---

# 十七、组件设计原则

所有组件必须：

1. 支持 Light Theme；
2. 为未来 Dark Theme 保留 Token 化能力；
3. 不直接硬编码颜色；
4. 优先使用 CSS Variables；
5. 复用统一 spacing；
6. 复用统一 typography；
7. 复用统一 radius；
8. 保持响应式设计。

例如禁止：

```tsx
<div className="bg-[#3F625F]">
```

优先：

```tsx
<div className="bg-primary">
```

颜色由全局 Theme 控制。

---

# 十八、Design Token 优先

所有核心视觉变量统一放入 Theme。

至少包括：

```text
Background
Surface
Text
Primary
Secondary
Accent
Border
Danger
Success

Radius

Spacing

Font

Chart Palette
```

未来改变整体 UI 时，应主要通过修改 Design Tokens 完成，而不是逐页修改组件。

---

# 十九、页面密度

Life OS 应采用：

**中低信息密度。**

企业系统更强调：

```text
单位屏幕展示多少信息
```

Life OS 更强调：

```text
人能否快速理解当前生活状态
```

因此适当增加：

- 留白
- 行距
- Section 间距

不要为了显示更多数据压缩布局。

---

# 二十、Codex 实现时的审美判断原则

如果存在多个设计方案，按照以下优先级判断：

```text
信息清晰
>
视觉克制
>
使用舒适
>
现代感
>
东方气质
>
视觉炫技
```

任何“看起来更酷”但降低长期使用舒适度的设计都应舍弃。

---

# 二十一、需要避免的常见 AI 前端风格

Codex 不要生成以下典型模板化设计：

- 大量 Gradient
- 紫蓝色 AI SaaS 风格
- Glow
- Glassmorphism
- 超大圆角
- 每一块都是 Card
- 巨大 Hero
- 大面积 Emoji
- 彩色 Icon Background
- Neon
- 大量 Badge
- 过多渐变按钮
- 复杂背景纹理
- 视觉装饰优先于信息

尤其禁止把 Life OS 做成：

**典型“AI Dashboard Template”。**

---

# 二十二、最终视觉关键词

在所有 UI 决策中保持以下关键词：

```text
现代
东方
青黛
天青
宣纸
墨色
留白
自然
轻盈
克制
安静
活力
秩序
长期使用
```

理想最终效果：

**第一眼是优秀的现代 Web Application；仔细使用后能够明显感受到一种克制、清雅而有生命力的东方审美。**

它应该像一个真正属于用户自己的：

**数字书房 + 生活仪表盘 + 个人操作系统。**

而不是一个换了中国风主题色的 SaaS 后台。
