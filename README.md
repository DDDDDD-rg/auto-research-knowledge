# 自动研究知识库

一个按研究问题组织工作的 Codex skill：检索已有知识、精读文献、核查计算复现，将证据应用于当前研究，并维护项目自己的 Markdown 知识库。

调用名称：auto-research-knowledge。

## 2026-10-26 更新

- 新增多对话并发归档：独立草稿、短期写锁和SHA-256版本检查，避免旧稿覆盖后来版本。
- 发生冲突时保留基准与双方草稿；支持备份、写入失败回滚和进程中断恢复。
- 新增14项行为测试，并更新初始化流程、项目规则示例和操作说明。
- 写入工具使用Python 3.9+标准库；普通查库继续沿用原来的工作方式。

## 工作方式

- 日常研究讨论、结果解释和方案建议自动查已有知识库，无需每次手动调用；按问题读取相关内容。
- 结合模型已有知识、实际项目文件和必要的网页查证，关键判断标明实际出处。
- 用户明确要求时，再开展系统性文献搜集、全文精读、批量归档或计算复现。
- 以一个研究问题为单位形成证据整理、方法分析和研究建议，文献篇数按需要决定。
- 自主执行轻量本机复现；长时计算或大量下载前先说明具体资源需求。
- 记录原文出处，区分论文结果、作者解释、研究假设与实际计算结果。

普通查库问答不自动转成已核验的文献笔记；正式阅读、复现或明确要求更新后，再维护相关记录和索引。这套流程通过项目规则和 skill 指令执行，未设置每轮强制检索的程序检查。

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

初始化会创建缺失的 Research_Knowledge 目录，再通过并发归档工具将空白模板写入缺失入口；已有知识文件保留原样。

4. 如果希望后续日常研究讨论自动读取知识库，可将 [AGENTS.example.md](AGENTS.example.md) 中适用的规则合并到目标项目的 AGENTS.md。

此安装方式作用于选择的项目。其他项目需要时再单独安装；不要求用户级安装。

## 多对话同时工作

不同对话可以同时阅读和编辑独立草稿，正式归档使用短暂写锁并核对版本。若另一对话已经修改同一文件，工具会拒绝旧版本覆盖，保留基准、自己的草稿和冲突时版本，合并后再归档。

正式归档需要Python 3.9+，无需安装额外Python包。命令和恢复方式见[并发写入规范](.agents/skills/auto-research-knowledge/references/concurrency.md)。所有写入者都需遵守此流程；已有对话更新skill后，应在下一次归档前重新读取规范。独立worktree和不同机器需另行同步。

目标项目使用Git时，将以下本地工作目录合并进原有 `.gitignore`：

```gitignore
/Research_Knowledge/_coordination/
/.knowledge-write-tests/
```

在本仓库根目录可运行 `python .agents/skills/auto-research-knowledge/scripts/test_knowledge_write.py` 验证机制。测试使用独立临时项目，包含真实双进程争写、同名新建及中断恢复。

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
- [并发写入规范](.agents/skills/auto-research-knowledge/references/concurrency.md)：独立草稿、冲突合并及恢复。
- [写入工具](.agents/skills/auto-research-knowledge/scripts/knowledge_write.py)与[行为测试](.agents/skills/auto-research-knowledge/scripts/test_knowledge_write.py)：本地协调与验证。
- [空白知识库模板](.agents/skills/auto-research-knowledge/assets/knowledge-base/INDEX.md)：索引、项目地图和决策记录。
- [项目规则示例](AGENTS.example.md)：按需合并的日常查库约定。

研究任务由skill指令与Codex当时可用的搜索、文件和计算工具执行；正式知识归档由附带Python脚本协调。全文获取范围、输入数据与实际运行环境记录在具体任务中。

## 下载与更新

在 GitHub 仓库页面选择 Code → Download ZIP，或使用 Git 克隆。本仓库作为下载与使用入口，不接受 Pull Request。

更新时比较并替换目标项目中的 skill 文件，保留使用者已经积累的 Research_Knowledge。空白模板用于缺失文件的初始化，不覆盖已有知识。

## 官方参考

- [Codex skill 的发现和使用](https://learn.chatgpt.com/docs/build-skills)
- [项目 AGENTS.md](https://learn.chatgpt.com/docs/agent-configuration/agents-md)
