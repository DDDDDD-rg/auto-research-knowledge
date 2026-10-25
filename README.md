# 自动研究知识库

一个按研究问题组织工作的 Codex skill：检索已有知识、精读文献、核查计算复现，将证据应用于当前研究，并维护项目自己的 Markdown 知识库。

调用名称：auto-research-knowledge。

## 工作方式

- 日常讨论先查已有知识库。
- 用户明确要求时，再检索新文献、精读全文或运行复现。
- 以一个研究问题为单位形成证据整理、方法分析和研究建议，文献篇数按需要决定。
- 自主执行轻量本机复现；长时计算或大量下载前先说明具体资源需求。
- 记录原文出处，区分论文结果、作者解释、研究假设与实际计算结果。

这是通用分享版，研究领域和数据入口由使用者在自己的项目中确定，附带的知识库模板为空白。

## 在一个项目中使用

1. 下载本仓库 ZIP 或克隆仓库。
2. 将 [.agents/skills/auto-research-knowledge](.agents/skills/auto-research-knowledge/SKILL.md) 的整个文件夹复制到目标项目同名位置。已有同名 skill 时先比较版本，按需要合并。
3. 在目标项目的 Codex 对话中发送：

~~~text
使用 $auto-research-knowledge，为当前项目初始化知识库。
我的研究主题是：……
目前最想解决的问题是：……
这次只建立入口和问题地图。
~~~

初始化会将 skill 内的空白模板复制到目标项目的 Research_Knowledge，仅补充缺失文件。

4. 如果希望后续日常研究讨论自动读取知识库，可将 [AGENTS.example.md](AGENTS.example.md) 中适用的规则合并到目标项目的 AGENTS.md。

此安装方式作用于选择的项目。其他项目需要时再单独安装；不要求用户级安装。

## 调用示例

查已有知识：

~~~text
使用 $auto-research-knowledge，查看已有知识库中哪些证据与这个结果有关。
~~~

检索与精读：

~~~text
使用 $auto-research-knowledge，围绕【一个明确研究问题】检索并精读文献，更新知识库，并说明对现有研究的参考。
~~~

复现：

~~~text
使用 $auto-research-knowledge，复现这篇论文指定的图表或方法，保存环境、代码、参数和结果对照。
~~~

## 文件组成

- [SKILL.md](.agents/skills/auto-research-knowledge/SKILL.md)：触发条件、工作流程、知识维护和交付标准。
- [文献与证据规范](.agents/skills/auto-research-knowledge/references/literature.md)：阅读范围、出处和证据链。
- [复现规范](.agents/skills/auto-research-knowledge/references/reproduction.md)：资源估算、实际运行及对照标准。
- [空白知识库模板](.agents/skills/auto-research-knowledge/assets/knowledge-base/INDEX.md)：索引、项目地图和决策记录。
- [项目规则示例](AGENTS.example.md)：按需合并的日常查库约定。

本 skill 的核心为文字指令，研究任务通过 Codex 当时可用的搜索、文件和计算工具执行。全文获取范围、输入数据与实际运行环境记录在具体任务中。

## 下载与更新

在 GitHub 仓库页面选择 Code → Download ZIP，或使用 Git 克隆。本仓库作为下载与使用入口，不接受 Pull Request。

更新时比较并替换目标项目中的 skill 文件，保留使用者已经积累的 Research_Knowledge。空白模板用于缺失文件的初始化，不覆盖已有知识。

## 官方参考

- [Codex skill 的发现和使用](https://learn.chatgpt.com/docs/build-skills)
- [项目 AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
