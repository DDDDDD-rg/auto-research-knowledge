# 多对话并发写入

适用：同一本地项目目录中，创建、修改、归档知识文件及同步共享导航。普通查库和文献阅读可并行，无需持有写锁。正式写入前每轮重新读取本页，不沿用旧对话中已缓存的写入流程。

## 写入约定

所有对话使用 `scripts/knowledge_write.py`。正式文件不再用 `apply_patch` 的 Add File、Set-Content 或直接覆盖来归档；这些工具只编辑该次运行的 `draft` 文件。使用 Python 3.9+ 和标准库，无服务、网络或额外依赖；脚本路径相对项目根目录。

工具提供的是协作式保护：各写入者必须遵守此入口。它不拦截编辑器或绕过工具的直接写入，也不跨独立 worktree、云端副本或机器协调。

### 1. 创建独立运行并取得当前版本

PowerShell，从项目根目录运行。`$writerPython` 指向本机可用 Python；`$writerScript` 指向本 skill 内脚本。不要假定其他机器具有相同解释器绝对路径。

```powershell
$writerPython = 'python'
$writerScript = '.agents/skills/auto-research-knowledge/scripts/knowledge_write.py'
$writerRun = (& $writerPython $writerScript begin --owner '当前对话ID/任务名' | ConvertFrom-Json).run
& $writerPython $writerScript checkout --run $writerRun `
  --path 'Research_Knowledge/papers/作者_年份_短题名.md' `
  --path 'Research_Knowledge/INDEX.md' `
  --path '.gitignore'
```

检查每条命令的退出码。`checkout` 返回每个草稿的绝对路径，并保存当时的基准版本；文件不存在时记录为空。接下来读取返回的草稿作为编辑基准，不把早先读到的整份旧文档覆盖到新快照。仅修改属于本轮证据和授权范围的段落。

每个对话/任务有独立且随机的 run ID、`base`、`draft`。同一 run 只由一个写入者使用；重复 checkout 同一路径会拒绝，避免破坏草稿。正式笔记、INDEX及主题/问题更新应在同一 run 内准备；采用放行清单的项目同时准备新增笔记的 `.gitignore` 精确规则，其他项目沿用既有忽略策略。未使用Git也能归档，示例中的 `.gitignore` 参数可省略。按研究问题组织归档批次。

首次初始化时，先只创建缺失的 Research_Knowledge 目录，再为缺失的 INDEX.md、PROJECT_MAP.md、DECISIONS.md checkout，将模板内容填入 draft 后归档。两个任务同时初始化时，“原本不存在”也会参与版本检查。已有入口保持原样。

大批阅读时可先独立写论文草稿；临近归档再 checkout 最新共享入口，把本轮新增信息合入。不要为了避免冲突将整个索引换成自己旧上下文里的版本。

### 2. 检查并归档

```powershell
& $writerPython $writerScript check --run $writerRun
& $writerPython $writerScript commit --run $writerRun
```

`commit` 会重新检查，而不依赖前一次 `check` 的结果。它短暂持有项目写锁，在锁内比对正式文件与基准版本的 SHA-256；整个批次预检通过后才替换正式文件。临时文件在同目录写完并刷新后以 `os.replace` 替换，避免读取到半份文档。阅读和草稿编辑不占写锁。

这里的 commit 是“本地文档归档”，不执行 Git add、Git commit 或 push。不要混淆这两种提交。

### 3. 处理结果

| 退出码/状态 | 操作 |
|---|---|
| 0 / committed | 本批归档完成；原版本保留在该 run 的 base，归档字节在 publish |
| 0 / no_changes | 无内容变化；尚未归档新内容 |
| 0 / already_committed | 该 run 已完成，不会再次覆盖之后的修改 |
| 3 / conflict | 正式文件已变；整个批次不写入。保留旧 base、自己的 draft 和冲突时的当前版本 conflict |
| 4 / busy | 写锁忙，默认最多等待15秒；可稍后重试同一命令，单次等待上限60秒 |
| 5 / recovery_required | 上一次写入中断。先 status 查看，再核对并 recover 指定运行 |
| 2 / error | 检查参数、路径、编码或I/O错误；修正后按状态处理 |

冲突时创建新的 run，checkout 最新正式文件，逐段比较旧 `base`、自己的 `draft` 与最新版本，保留双方有效证据后编辑新草稿。不要删除别人段落以通过检查；没有 `--force` 或自动整篇覆盖选项。研究解释发生矛盾时，保留来源、适用条件和待决定项，不能由脚本替代科学判断。

## 中断与恢复

运行记录、备份、冲突和锁位于 `Research_Knowledge/_coordination/`。使用Git的目标项目应将该目录加入忽略规则（本分享仓库已整体忽略生成的 Research_Knowledge）；测试目录 `.knowledge-write-tests/` 也保持忽略。不要将运行记录、备份和锁加入版本管理，也不要自动清理未合并的冲突草稿。

锁由操作系统持有，进程退出/终止即释放；锁文件永久保留，不按时间判断陈旧、不删除锁文件来抢锁。多文件归档不是数据库级一次性可见：遵守工具的写入者/checkout 在锁下读取完整批次，外部直接读文件的程序可能短暂看到前后版本混合。需要一致快照时用同一次 checkout。

工具在第一份正式文件写入前记录 applying 日志。普通写入错误会尝试回滚；进程突然中断后，后续归档会阻止继续写，直到处理恢复：

```powershell
& $writerPython $writerScript status
& $writerPython $writerScript recover --run '需要恢复的run ID'
```

recover 将该未完成批次恢复至 base，保留所有草稿。若发现中断后又有外部修改，则停止恢复、保留外部内容，报告 recovery_conflict，逐项核对，不自动覆盖。

## 可写范围和验证

工具只接受知识入口、papers/topics/questions 的Markdown、reproductions的文本代码/配置，以及协调更新所需的根 AGENTS.md、README.md、.gitignore；排除原始数据、local、缓存、隐藏目录及越界/链接路径。它不提供删除正式笔记的操作。

用临时项目运行行为验证：

```powershell
& $writerPython '.agents/skills/auto-research-knowledge/scripts/test_knowledge_write.py'
```

测试包含两个真实进程争写同一文件、新建同名笔记、批次冲突、锁超时、终止进程释放锁、写入中断恢复、I/O失败回滚和路径范围。夹具在当前目录 `.knowledge-write-tests/` 下创建随机临时项目并于每例测试后清理，不修改正式研究笔记；可用环境变量 KNOWLEDGE_TEST_TMP 指定其他可写测试目录。
