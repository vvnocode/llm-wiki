# Wiki 目录

个人全局知识库的根索引。**两级索引**：本页只列分区与入口，各分区（尤其每个项目子目录）维护自己的明细索引，防止本页随项目增多而膨胀。写法见 `~/.llm-wiki/docs/schemas/wiki.md`，分层判据见 `~/.llm-wiki/docs/schemas/分区与共享.md`。

- [演进日志](log.md)：按月索引。

## 项目分区

每个外部项目一个子目录，各自维护 `index.md`。实例化后在下表登记。

| 项目 | 入口 | 一句话 |
|---|---|---|
| _（实例化后登记）_ | `projects/<项目名>/index.md` | |

## 公共层

| 分区 | 收什么 |
|---|---|
| [concepts/](concepts/README.md) | 跨项目可复用的概念与机制 |
| [entities/](entities/README.md) | 人、设备、外部系统 |
| [operations/](operations/README.md) | 真实故障与案例 |
| [decisions/](decisions/README.md) | 为什么这样设计，含被否方案 |
| [risks/](risks/README.md) | 待核验与知识缺口 |

## 学习

[learning/](learning/README.md)：学习中心（paths / chapters / labs / assessments）。讲义生成物在 `~/.llm-wiki/outputs/learning/`。

## 私有区

`private/` 物理不出本机，内容不列入本索引。

## 来源

- `README.md`：工作台结构说明。

## 最后核验

- 2026-08-27
