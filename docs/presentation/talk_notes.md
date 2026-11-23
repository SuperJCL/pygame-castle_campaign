# Castle Siege 答辩图讲解稿

两张投屏图分别是代码架构图和一次开火流程图。图上只放关键文件名，职责用中文写，每个说法都能在下面的「源码出处」里找到对应代码。

| 文件 | 用途 |
|---|---|
| `architecture.png` / `fire_flow.png` | 投屏用，16:9，3840×2160，带标题和底部图例 |
| `architecture.svg` / `fire_flow.svg` | 只有图本身，可插进自己的幻灯片；文字是 SVG 原生文本，插进 PPT 也能显示 |
| `architecture.mmd` / `fire_flow.mmd` | Mermaid 源码，修改后可重新渲染 |

## 图 1：代码架构

> 1. 我们把代码分成四块：界面、战斗规则、AI、绘制。图上的四种颜色分别对应这四块。
> 2. 深蓝粗线是主线。鼠标和键盘的输入先到 `main.py`，它只负责读输入、推进每一帧、决定什么时候开火。玩家和 AI 提交战斗行动都走同一个入口，就是 `battle.py` 的 `perform_action()`。
> 3. Battle 按 `characters.py` 里的职业数值和 `castle.py` 里的掩体处理回合、碰撞和伤害，再把发生的事写成事件交回界面。界面据此让 `drawing.py` 和 `sound.py` 画特效、放音效，自己不再计算伤害。
> 4. 轮到电脑时，`ai.py` 先在 deepcopy 出来的 Battle 副本里试招、打分。选好以后，它仍然通过同一个 `perform_action()` 出招，所以电脑和玩家遵守同一套规则。
> 5. 灰色细虚线表示 AI 还直接用到角色和掩体模块，用来选队、布防、估算伤害。
> 6. 战斗规则和 AI 这两块都不 import pygame，所以核心规则和 AI 可以不开 Pygame 窗口，直接测试。

## 图 2：一次开火

> 1. 角度在按下的那一刻就锁定了。Classic 模式记下当时的角度和火力；Reflex 模式锁住按下时正在摆动的角度；电脑等满 40 帧，选出射击方案后，炮口立刻转到计划的角度。
> 2. 这三种情况都由界面 `main.py` 创建一个 `PendingShot`（类定义在 `animation.py`），把角度、火力、角色和动作一起记下来，之后不再改变。
> 3. 角色先用 20 帧跑到炮台，跑动期间不能重新瞄准或出招。到达炮台才调用 `Battle.perform_action()` 发射：普通攻击 1 枚；齐射同时发 3 枚；空爆先发 1 枚，到最高点再分成 5 枚。
> 4. 之后 `Battle.update()` 每帧推进每一枚炮弹。命中的那枚立刻移出列表，并当场造成伤害，所以伤害是每枚各算各的。
> 5. 炮弹列表变空的那一帧，才调用一次 `_end_attack()`，把整次攻击的经验算成一份，再由 `_finish_turn()` 发经验、判胜负，结束对局或者换回合。
> 6. 列表空了以后，`update()` 一开头就直接返回；炮弹还在飞时，`why_not_allowed()` 也会拒绝任何新行动。所以不管是 3 枚还是 5 枚炮弹，都只结算一次。

## 可能被问到

- **跑向炮台的动画会不会改变落点？** 不会。动画只决定什么时候发射。`fire_pending_shot()` 用的是 `PendingShot` 里记下的角度和火力。角色跑回原位和炮弹飞行可以同时进行，要等角色归位、而且没有炮弹在飞，才重新开放输入。
- **齐射三枚都命中，会拿三份经验吗？** 不会。`_explode()` 只记两件事：这次攻击有没有命中，击倒了几个人。`_end_attack()` 最后只算一次：有命中给 10 点，每击倒一人再加 20 点。
- **电脑试招会不会改到真正的对局？** 不会。`imagine()` 是在 `copy.deepcopy(battle)` 得到的副本上调用 `perform_action()`。真正的 Battle 只在 `carry_out()` 时才改变。

## 与 `presentation_code_map.md` 的对照

原文件没有改动。核对结果：模块分工、事件交回界面、AI 在副本里试招、菜单和暂停流程、角色跑回与炮弹飞行可以重叠，这些都和现在的代码一致。新图补上了四处原图没画出来的内容：

1. `ai.py` 除了用 `battle.py`，还直接用 `characters.py` 和 `castle.py`。原架构图只画了 `ai.py → battle.py`。
2. 角度锁定的时刻，以及 Classic、Reflex、AI 三种锁定方式。
3. 到达炮台才发射：齐射在出膛时同时发 3 枚；空爆出膛时只有 1 枚，到顶点才由 `_split()` 分成 5 枚。
4. 只结算一次的具体做法：列表变空才调用 `_end_attack()`，`update()` 见到空列表就返回，炮弹在飞时不接受新行动。

如果要用新图替换原文件里的两段 Mermaid，把 `.mmd` 整段复制过去即可，开头两条 `---` 之间的配置也要一起复制。

## 源码出处

| 图上的说法 | 代码位置 |
|---|---|
| `PendingShot` 由界面创建 | 类定义在 `animation.py`；`main.py` 的 `do_action()`（玩家）和 `update_ai()`（电脑）创建它，`fire_pending_shot()` 使用它 |
| Classic：按下时记下角度和火力 | `main.py` `Game.do_action()`：`PendingShot(side, index, action, cannon.angle, cannon.power)` |
| Reflex：锁住摆动角度 | `main.py` `swing_aim()` 每帧让炮口跟随 `reflex_aim.py` 的 `AimSwing.angle()`；`do_action()` 记下当前角度，并设置 `locked_shot`；之后 `controls_locked()` 为真，摆动停止 |
| AI：第 40 帧选方案，炮口立刻转向 | `main.py` `AI_DELAY_FRAMES = 40`；`update_ai()`：调用 `choose()` 后执行 `aim_cannon(plan.angle, plan.power)`，再建 `PendingShot(..., plan)` |
| 跑 20 帧，到达才发射 | `animation.py` `RUN_FRAMES = 20`；`CannonRun.step()` 到达时返回 True，随后调用 `Game.fire_pending_shot()` |
| 跑动期间不能重新瞄准或出招，暂停仍可用 | `controls_locked()` 在 `cannon_run.is_busy()` 时为真，瞄准和出招都被挡住；`handle_key()` 里 Esc 直接调用 `open_pause_menu()`，不检查 `controls_locked()` |
| 出招走 `perform_action()` | `fire_pending_shot()`：玩家先 `aim_cannon` 再 `Battle.perform_action()`；电脑通过 `AIController.carry_out()` 调用 `Battle.perform_action()` |
| 齐射同时发 3 枚；空爆先发 1 枚，到顶点再分成 5 枚 | `battle.py` `Battle._launch()`：每个 spread 调用一次 `cannon.fire()`，齐射的 `VOLLEY_SPREAD` 有 3 项，所以出膛时就是 3 枚；空爆出膛时是 1 枚母弹，`Battle._split()` 在它到顶点、`vy` 由负变为非负时，按 `AIRBURST_SPLIT` 的 5 项分成 5 枚 |
| 命中即移出列表、当场伤害 | `Battle.update()`：命中时执行 `projectiles.remove(shell)`，再调用 `_explode()` |
| 只结算一次 | `Battle.update()` 开头 `if not self.projectiles: return`，结尾 `if not self.projectiles: self._end_attack()`；有炮弹在飞时 `can_fire()` 为假，`why_not_allowed()` 因此拒绝新行动 |
| 经验、胜负、换回合 | `EXP_FOR_HIT = 10`，`EXP_FOR_DEFEAT = 20`；`_finish_turn()` 依次执行 `gain_exp()`、`check_winner()`，然后发出 `game_over` 或换回合 |
| AI 在副本里试招 | `ai.py` `imagine()`：先 `copy.deepcopy(battle)`，再在副本上调用 `perform_action()` |
| AI 直接用到角色和掩体 | `ai.py` 导入 `characters`：`ARCHETYPES` 用于选队，`calculate_damage` 用于估算伤害，`Knight`、`Engineer`、`Medic` 用于判断技能；导入 `castle`：`place_block` 等用于布防 |
| 规则和 AI 不 import pygame | 只有 `main.py`、`drawing.py`、`sound.py` 导入 pygame；对应测试是 `tests/test_battle.py` 的 `test_logic_modules_do_not_import_pygame` 和 `tests/test_ai.py` 的 `test_the_ai_module_does_not_import_pygame` |

实测（2026-11-22，在没有安装 Pygame 的 Python 3.11 上运行）：`tests.test_battle`、`tests.test_castle`、`tests.test_characters` 共 105 项通过；`tests.test_ai` 54 项通过；两次都没有跳过的测试。

## 导出说明

- 使用 Mermaid 11.4.1，与 M5 类图同一版本，在本机用 Chrome 无头模式渲染。
- 字体首选 Microsoft YaHei。别的电脑缺这个字体时，会换用 PingFang SC 或 Noto Sans CJK SC，字宽可能略有不同。
- PNG 的标题和底部图例是导出页面加上去的，`.mmd` 里没有。`.mmd` 能在任何支持 Mermaid 11 的工具里打开。
- 排版上有两个限制，已经写在 `.mmd` 的注释里。第一，带下划线的函数名要放在节点最后一行，否则下划线会贴到下一行中文。第二，连线上的标签只写短中文，因为 Mermaid 大约在 200px 处就会把标签折行。
