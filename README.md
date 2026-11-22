# 双台架探头比测与离线复核

仪表维护班用这套工具把白班的台架比测交给夜班质控。两座台架关闭后，质控员仍能用各自的实收件在共同设档下核定复测结论。次班勘误后，维护人员凭原报告号核对当时的结论和输入。

## 一班的工作

1. 白班从比测账取得每台架一至三对原读和校准项，调用 `record` 登记一版。
2. 白班用 `export` 选择具体修订，冻结其原读和校准关系。
3. 发行登记交给值班员固定 V1 字节件和出处。站件仅含设档名和逐对差值，原读、物理对身份和试片号留站。
4. 夜班用 `admit` 实收两件，关闭两个源连接。
5. 夜班用 `assess` 按台架提交实收号、闭设档域和阈值。
6. 中心计算共同设档下双侧精确 p 值的实际极值。
7. 定稿连同原请求和两件父件一起提交。维护班使用复测分类。
8. 次班以原修订为父版登记完整勘误，按新版号另行发行。
9. 中心可分别复核新版和旧版。重开后 `get_report` 按号交还原定稿及原父件。

## Python API

Python 3.11 标准库。调用方打开并关闭 SQLite 连接。每台架长期使用一份独立源账，中心另用一库保存实收和报告。各写入入口拥有自己的事务，进入时连接应处于空闲状态。同一连接应按顺序使用。库可重复初始化，已有修订、实收原字节和定稿全部保留。

| 入口 | 输入、输出与失败 |
| --- | --- |
| `bench.batches.record(store, batch)` | `RevisionStore` 加 `BatchInput(bench, batch, settings, pairs, parent_id=None)`。一至三条 `PhysicalPair(pair_id, specimen, left, right, left_unit, right_unit, calibration)`。`NamedCalibration(offset, coefficients)` 的名称必须与两个设档名完全一致。返回整型修订号。非法输入、重复对或错父版引发 `ValueError`。勘误提交完整的新版本。 |
| `issue.register.export(revisions, register, bench, revision_id)` | 返回 `IssuedEvidence`，含台架、发行号、修订号和 `wire` 字节。未知或不属指定台架的修订引发 `LookupError`。`IssueRegister.get(issue_id)` 领取已登记原件，缺号返回 `None`。 |
| `receipt.admit.admit(store, wire)` | 返回实收号。相同台架及发行号下，重送原字节返回原号。外层、正文无效或同号异件引发 `ValueError`。 |
| `review.evaluate.assess(receipts, archive, benches, receipt_ids, bounds, threshold)` | 两张按 `benches` 顺序排列的实收号，`bounds` 为按名提供闭区间的映射，`threshold` 为 `[0,1]` 的有理数。返回 `FinalReport`。缺件引发 `LookupError`，错台架、名称、区间或阈值引发 `ValueError`。可选 `before_commit` 无参回调用于在已写入且未提交时中止事务，异常经回滚后向上传递。回调不得自行控制事务。 |
| `report.retrieve.get_report(archive, report_id)` | 返回签存时的 `FinalReport`，未知正整数号返回 `None`。不访问源账或重新核算。 |

源连接分别调用 `RevisionStore(connection).initialize()` 和 `IssueRegister(connection).initialize()`。中心连接调用 `ReceiptStore(connection).initialize()` 和 `ReportArchive(connection).initialize()`。`FinalReport` 的 `snapshot` 含原请求的有理数规范值、`minimum_p`、`maximum_p` 和 `verdict`，`parents` 按请求顺序记录台架、实收号、发行号和修订号。

## 测量、站件与裁决

源账接受 `mm`、`cm`、`um`。双侧原读分别换算到毫米，然后左减右，加校准偏置和各具名设档乘对应系数。偏置和系数按毫米口径给出。原读、偏置、系数、边界和阈值接受整数、`Fraction` 或 `Fraction` 可解析的有理字符串。浮点数、布尔值、空值和零分母拒绝。物理对按身份检查唯一性，同值异对分别计数。

V1 外层为 UTF-8 JSON，字段为 `version`、`bench`、`issue_id`、`revision_id`、`body`、`sha256`。发行和修订号在源账内分配，发行身份为台架及其发行号。`body` 是 JSON 文本，摘要是其 UTF-8 字节的 SHA-256。正文含 `settings` 和 `differences`。每条差值由常量及沿 `settings` 次序的两个系数组成，均为有理字符串。数组一项对应一个物理对，即使同值也保留所有项。中心按名称重排系数，保留并以原始字节识别重送。

中心按同一组设档合并两台架的差值。零差值剔除，绝对值并列项取平均秩。所有非零物理对独立等权翻符号，绝对符号秩和达到实测值的比例为双侧 p 值。合法样本全零时取 1。矩形、线段和点都使用闭域，边界、零差值和并列状态参与极值。最大 p 值不大于阈值时为 `all`，最小 p 值大于阈值时为 `none`，其余为 `some`。所有计算和翻转计数确定且精确。

## 回归与演示

```sh
python3 -B check_project.py
python3 -B demo.py
```

回归入口执行 `tests` 包的完整 `unittest` 套件。`test_issue.py` 检查登记、单位换算、冻结、站件隐私和非法勘误，`test_receipt.py` 检查实收、重送与错件隔离，`test_offline.py` 检查闭域、统计量、裁决和失败回滚，`test_amend.py` 检查同边缘勘误、指定旧版和重开核账。演示使用 `examples` 的三份固定输入，经真实 API 在临时数据库中复核，输出原版 `[3/4,1]`、勘误版 `[1/2,1]` 和重开后按号领取的原报告及父件。
