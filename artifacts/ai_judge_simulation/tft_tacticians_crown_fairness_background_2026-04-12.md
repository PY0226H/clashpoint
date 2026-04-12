# 模拟背景文档：云顶之弈全球总决赛赛制是否公平？

- 文档用途：作为后续 AI_judge 全流程模拟的“背景知识文档”输入。
- 辩题：云顶之弈全球总决赛（TFT Tactician's Crown）赛制是否公平？
- 信息检索日期：2026-04-12（美国太平洋时间）。
- 说明：本稿优先使用 Riot/TFT 官方发布信息；“公平”属于价值判断，本文仅整理事实与可辩论焦点，不预设结论。

## 1) 最新一届全球总决赛（Lore & Legends，2026-03）核心事实

1. 官方赛事名称为 Lore & Legends Tactician's Crown，比赛时间为 2026-03-27 至 2026-03-29。[官方 Event Primer](https://teamfighttactics.leagueoflegends.com/en-us/news/esports/lore-legends-tacticians-crown-event-primer/)
2. 参赛规模为 40 人，3 天赛程，Day 1 为 40 人 6 局，Day 2 为 32 人 7 局，Day 3 为 8 人决赛。[官方 Event Primer](https://teamfighttactics.leagueoflegends.com/en-us/news/esports/lore-legends-tacticians-crown-event-primer/)
3. 基础积分为 8/7/6/5/4/3/2/1（第 1 到第 8 名）。[官方 Event Primer](https://teamfighttactics.leagueoflegends.com/en-us/news/esports/lore-legends-tacticians-crown-event-primer/)
4. Day 1 到 Day 2 采用累计分机制（不重置），并在 Day 2 发生多轮淘汰与晋级（32→24→16→12→8）。[官方 Event Primer](https://teamfighttactics.leagueoflegends.com/en-us/news/esports/lore-legends-tacticians-crown-event-primer/)
5. Day 3 决赛使用 Checkmate：选手先达到 20 分后，还需再拿 1 次单局第一才能夺冠。[官方 Event Primer](https://teamfighttactics.leagueoflegends.com/en-us/news/esports/lore-legends-tacticians-crown-event-primer/)
6. 该届最终冠军为 AMER 赛区的 Darth Nub（官方战报发布时间 2026-04-01）。[官方战报](https://teamfighttactics.leagueoflegends.com/en-us/news/esports/darth-nub-wins-the-lore--legends-tacticians-crown/)

## 2) 名额与资格路径（与“公平性”直接相关）

1. 在 2025-09 的 K.O. Coliseum Tactician's Crown 公告中，40 人名额拆分为：TPC 直通 12 席 + 各大区最低保底席位（APAC 8、CN 8、AMER 6、EMEA 6）。[官方公告](https://teamfighttactics.leagueoflegends.com/en-us/news/esports/ko-coliseum-tacticians-crown-announcement/)
2. 2026-01 的 Set 16 TPC 规则更新提到：除三站 Cup 冠军外，Pro Points 总榜第 1 也可直通 Tactician's Crown；同时对 Regional Finals 的上下半区准入做了调整（Top 16 直进 Week2、Bottom 4 去 Play-Ins）。[官方规则文](https://teamfighttactics.leagueoflegends.com/en-us/news/esports/set-16-tft-pro-circuit-everything-you-need-to-know/)
3. 2026-02 的 Regional Finals 官方说明显示：Lore & Legends 周期里，各区晋级 Crown 的席位并非完全固定平均，且会受 TPC 既有出线结果影响（例如文中列出 AMER “5 + 3 additional”）。[Regional Finals 官方文](https://teamfighttactics.leagueoflegends.com/en-ph/news/esports/regional-finals-everything-you-need-to-know-march/)
4. 官方在 2024-08 的全球赛制更新中明确提到：将全球总决赛规模从 32 扩至 40，原因之一是回应“赛区代表性不足”的反馈，并引入基于历史表现（平均名次）与卫冕冠军条件的额外席位逻辑。[官方更新](https://teamfighttactics.leagueoflegends.com/en-gb/news/esports/tft-esports-competitive-updates-magic-n-mayhem/)

## 3) 赛制设计中的“公平”争议焦点（供正反方论证）

1. 代表性公平：名额分配是否兼顾“强赛区成绩导向”与“全球赛区代表性导向”。
2. 路径公平：TPC 直通、Regional Finals、本地赛区通道并存时，不同路径的出线难度是否等价。
3. 样本公平：Day 1+Day 2 累计多局是否足够降低偶然性，是否能更好筛出“稳定强者”。
4. 决赛公平：Checkmate 机制强调“登顶必须吃鸡”，是更符合“冠军标准”还是引入额外波动。
5. 赛程公平：Carry-over（跨日累计分）对前期优势的放大，是否会压缩后段选手翻盘空间。
6. 分组公平：Snake draft 与定期 reshuffle 是否足够避免“死亡组”长期固化。

## 4) 可直接用于模拟对话的“事实卡片”

1. “全球总决赛已是 40 人而非 32 人，官方解释是为了提升代表性并回应反馈。”
2. “当前体系同时奖励长期稳定表现（Pro Points）与阶段性爆发（Cup 冠军/区域赛）。”
3. “总决赛并非只看总分，冠军必须在达标后完成单局第一（Checkmate）。”
4. “部分阶段积分累计不重置，强调全程稳定性。”
5. “席位存在保底 + 业绩导向的混合分配，不是完全平均配额。”

## 5) 在 AI_judge 模拟中的建议使用方式

1. 将本文作为 `background_document`（背景材料）输入。
2. 正方可主打“多轮累计 + Checkmate 的冠军门槛 + 扩编提升代表性”。
3. 反方可主打“路径复杂且不对称 + 名额动态受历史结果影响 + Checkmate 终局波动”。
4. 评审标准建议至少包含：代表性、公平机会、稳定性、可解释性、观赏性与竞技性平衡。

## 6) 参考来源（按发布时间）

1. 2024-08-01：TFT Esports Competitive Updates - Magic n' Mayhem  
   https://teamfighttactics.leagueoflegends.com/en-gb/news/esports/tft-esports-competitive-updates-magic-n-mayhem/
2. 2025-09-30：K.O. Coliseum Tactician's Crown Announcement  
   https://teamfighttactics.leagueoflegends.com/en-us/news/esports/ko-coliseum-tacticians-crown-announcement/
3. 2026-01-06：Set 16 TFT Pro Circuit: Everything You Need to Know  
   https://teamfighttactics.leagueoflegends.com/en-us/news/esports/set-16-tft-pro-circuit-everything-you-need-to-know/
4. 2026-02-26：Regional Finals: Everything You Need To Know  
   https://teamfighttactics.leagueoflegends.com/en-ph/news/esports/regional-finals-everything-you-need-to-know-march/
5. 2026-03-19：Lore & Legends Tactician's Crown Event Primer  
   https://teamfighttactics.leagueoflegends.com/en-us/news/esports/lore-legends-tacticians-crown-event-primer/
6. 2026-04-01：Darth Nub Wins the Lore & Legends Tactician's Crown!  
   https://teamfighttactics.leagueoflegends.com/en-us/news/esports/darth-nub-wins-the-lore--legends-tacticians-crown/
