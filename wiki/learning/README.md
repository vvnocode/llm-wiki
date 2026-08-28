# learning/：学习模块

系统学习的编译区，由 `llm-wiki-learn` skill 维护：

```
learning/
├── index.md        # 学习中心：在学什么、进度、下一步
├── paths/          # 学习路线：目标 → 章节序列
├── chapters/       # 教材式章节（系统化讲解，带来源）
├── labs/           # 实践练习
└── assessments/    # 测验与掌握检查
```

硬规则：**未通过 assessments 验收，不得把任何主题标记为「已掌握」**。生成的讲义、导出的教材放 `~/.llm-wiki/outputs/learning/`（可再生成，不是 wiki）。子目录按需创建，不预建空目录。
