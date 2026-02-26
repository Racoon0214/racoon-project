from collections import defaultdict

# 定义项目和人
projects = [
    "项目1:北极熊头仿生控制技术研发",
    "项目2:基于十二生肖仿生机械转马类的装置研发",
    "项目3:球幕生态系统模拟与技术研发",
    "项目4:多模态融合的智能驾舱技术研发",
    "项目5:巨型机器人精准控速、稳定滑行装备研发",
    "项目6:导向型多任务协同决策与智能调度技术研发",
    "项目7:巨型机器人高刚性运动仿生机械手臂装备研发",
    "项目8:大型智能交互仿生装备决策控制大模型技术研发",
    "项目9:多模态交互与混合驱动控制的仿生装备研发"
]

# 人员信息：姓名、职位、是否待招
people = [
    {"name": "刘贞", "position": "部长", "is_recruit": False},
    {"name": "王星霖", "position": "机械设计", "is_recruit": False},
    {"name": "机械设计待招", "position": "机械设计", "is_recruit": True},
    {"name": "陈世超", "position": "电气", "is_recruit": False},
    {"name": "刘洋", "position": "工业设计", "is_recruit": False},
    {"name": "张佳鑫", "position": "工业设计", "is_recruit": False},
    {"name": "宋鹏", "position": "软件工程师", "is_recruit": False},
    {"name": "迟佳林", "position": "软件工程师", "is_recruit": False},
    {"name": "软件工程师待招", "position": "软件工程师", "is_recruit": True}
]

# 每个项目需要的人数
project_required_people = {
    projects[0]: 4,  # 项目1
    projects[1]: 4,  # 项目2
    projects[2]: 3,  # 项目3（特殊）
    projects[3]: 4,  # 项目4
    projects[4]: 4,  # 项目5
    projects[5]: 3,  # 项目6（特殊）
    projects[6]: 4,  # 项目7
    projects[7]: 4,  # 项目8
    projects[8]: 4  # 项目9
}

# 项目负责人（已在表格中填写，工作比重固定）
project_leaders = {
    projects[0]: "刘贞",
    projects[1]: "陈世超",
    projects[2]: "宋鹏",
    projects[3]: "迟佳林",
    projects[4]: "刘贞",
    projects[5]: "刘贞",
    projects[6]: "王星霖",
    projects[7]: "刘贞",
    projects[8]: "刘贞"
}

# 项目负责人的工作比重（已在表格中填写）
leader_workloads = {
    projects[0]: 0.2,  # 刘贞
    projects[1]: 0.5,  # 陈世超
    projects[2]: 0.5,  # 宋鹏
    projects[3]: 0.5,  # 迟佳林
    projects[4]: 0.2,  # 刘贞
    projects[5]: 0.2,  # 刘贞
    projects[6]: 0.5,  # 王星霖
    projects[7]: 0.2,  # 刘贞
    projects[8]: 0.2  # 刘贞
}

# 按职位分组人员
mechanical_designers = ["王星霖", "机械设计待招"]
software_engineers = ["宋鹏", "迟佳林", "软件工程师待招"]
industrial_designers = ["刘洋", "张佳鑫"]
electrical_engineer = ["陈世超"]
manager = ["刘贞"]

print("开始智能分配...")

# 初始化分配结果
assignment = {proj: {} for proj in projects}
person_total_workload = {p["name"]: 0.0 for p in people}

# 步骤1: 分配所有项目负责人
for proj, leader_name in project_leaders.items():
    workload = leader_workloads[proj]
    assignment[proj][leader_name] = workload
    person_total_workload[leader_name] += workload
    print(f"已分配: {proj[:15]}... - {leader_name}: {workload:.2f}")

# 步骤2: 为每个项目补充人员到所需数量
for proj in projects:
    required_count = project_required_people[proj]
    current_count = len(assignment[proj])

    if current_count >= required_count:
        continue

    remaining_slots = required_count - current_count
    leader_name = project_leaders[proj]

    print(f"\n为{proj[:15]}...补充{remaining_slots}人 (已有{current_count}人):")

    # 根据项目类型确定需要补充的人员类型
    proj_str = proj.lower()

    # 判断项目类型
    is_mechanical = any(keyword in proj_str for keyword in ["机械", "机器人", "转马", "手臂", "滑行", "仿生装备"])
    is_software = any(
        keyword in proj_str for keyword in ["系统", "算法", "模型", "软件", "交互", "决策", "调度", "驾舱"])

    # 优先选择相关专业的人员
    candidates = []

    if is_mechanical:
        candidates.extend([p for p in mechanical_designers if p not in assignment[proj]])

    if is_software:
        candidates.extend([p for p in software_engineers if p not in assignment[proj]])

    # 添加工业设计人员（大多数项目都需要）
    candidates.extend([p for p in industrial_designers if p not in assignment[proj] and p not in candidates])

    # 添加电气工程师（如果需要）
    if is_mechanical:
        candidates.extend([p for p in electrical_engineer if p not in assignment[proj] and p not in candidates])

    # 如果没有足够的候选人，添加其他人员
    if len(candidates) < remaining_slots:
        all_people = [p["name"] for p in people]
        additional = [p for p in all_people if p not in assignment[proj] and p not in candidates and p != leader_name]
        candidates.extend(additional)

    # 选择候选人，优先选择当前总工作量较低的人员
    candidates_sorted = sorted(candidates, key=lambda p: person_total_workload[p])
    selected = candidates_sorted[:remaining_slots]

    # 计算每个非负责人的工作量
    leader_workload = leader_workloads[proj]
    remaining_workload = 1.0 - leader_workload

    if required_count == 3:  # 3人项目
        # 负责人已占0.5，剩余两人各0.25
        workload_per_person = remaining_workload / 2
    else:  # 4人项目
        # 负责人已占一定比重，剩余三人平均分配
        workload_per_person = remaining_workload / 3

    # 分配工作给选中的人员
    for person in selected:
        assignment[proj][person] = workload_per_person
        person_total_workload[person] += workload_per_person
        print(f"  补充: {person}: {workload_per_person:.2f}")

# 步骤3: 调整工作比重以满足每人总工作量为1.0（非待招人员）
print("\n\n步骤3: 调整工作比重...")

# 收集所有非待招人员
non_recruit_people = [p["name"] for p in people if not p["is_recruit"]]

# 计算需要调整的量
adjustments_needed = {}
for person in non_recruit_people:
    current_total = person_total_workload[person]
    diff = 1.0 - current_total
    if abs(diff) > 0.001:
        adjustments_needed[person] = diff
        print(f"  {person}: 当前{current_total:.2f}, 需要调整{diff:+.2f}")

# 进行多轮调整
max_iterations = 100
for iteration in range(max_iterations):
    adjustments_made = False

    for person, needed_diff in list(adjustments_needed.items()):
        if abs(needed_diff) < 0.001:
            continue

        # 找到该人员参与的项目
        person_projects = []
        for proj in projects:
            if person in assignment[proj]:
                person_projects.append(proj)

        if not person_projects:
            continue

        # 尝试调整
        adjustment_per_project = needed_diff / len(person_projects)

        # 检查调整是否可行（不会使其他条件不满足）
        feasible = True
        for proj in person_projects:
            # 获取项目信息
            leader_name = project_leaders[proj]
            required_count = project_required_people[proj]
            remaining_people_count = required_count - 1

            # 如果是负责人，不能调整工作比重（已固定）
            if person == leader_name:
                feasible = False
                break

            # 调整后的工作量必须在合理范围内
            new_workload = assignment[proj][person] + adjustment_per_project
            if new_workload <= 0 or new_workload > 0.5:  # 非负责人最多0.5
                feasible = False
                break

            # 调整后项目总工作量必须为1.0
            project_total = sum(assignment[proj].values()) + adjustment_per_project
            if abs(project_total - 1.0) > 0.01:
                # 需要调整其他人员的工作量以保持项目总工作量为1.0
                pass

        if feasible:
            # 执行调整
            for proj in person_projects:
                assignment[proj][person] += adjustment_per_project

            person_total_workload[person] += needed_diff
            adjustments_needed[person] = 0.0
            adjustments_made = True

    # 如果没有调整或已满足所有条件，退出循环
    total_adjustment_needed = sum(abs(diff) for diff in adjustments_needed.values())
    if total_adjustment_needed < 0.001 or not adjustments_made:
        break

# 步骤4: 验证分配结果
print("\n\n步骤4: 验证分配结果...")

# 检查每个项目的人员数量
all_valid = True
for proj in projects:
    required_count = project_required_people[proj]
    actual_count = len(assignment[proj])
    if actual_count != required_count:
        print(f"  ❌ {proj[:15]}...: 需要{required_count}人，实际{actual_count}人")
        all_valid = False
    else:
        print(f"  ✅ {proj[:15]}...: 人员数量正确({actual_count}人)")

# 检查每个项目的总工作量
print()
for proj in projects:
    project_total = sum(assignment[proj].values())
    if abs(project_total - 1.0) > 0.001:
        print(f"  ❌ {proj[:15]}...: 总工作量{project_total:.2f}，不是1.0")
        all_valid = False
    else:
        print(f"  ✅ {proj[:15]}...: 总工作量正确(1.0)")

# 检查非待招人员总工作量
print()
for person in non_recruit_people:
    total = person_total_workload[person]
    if abs(total - 1.0) > 0.001:
        print(f"  ❌ {person}: 总工作量{total:.2f}，不是1.0")
        all_valid = False
    else:
        print(f"  ✅ {person}: 总工作量正确(1.0)")

# 检查待招人员总工作量
print()
recruit_people = [p["name"] for p in people if p["is_recruit"]]
for person in recruit_people:
    total = person_total_workload[person]
    if total > 1.001:
        print(f"  ❌ {person}: 总工作量{total:.2f}，超过1.0")
        all_valid = False
    else:
        print(f"  ✅ {person}: 总工作量{total:.2f}，未超过1.0")

# 显示最终分配结果
print("\n\n最终分配结果:")
print("=" * 80)

for proj in projects:
    required_count = project_required_people[proj]
    print(f"\n{proj} (需要{required_count}人):")
    project_total = 0
    for person, workload in assignment[proj].items():
        person_info = next(p for p in people if p["name"] == person)
        status = "待招" if person_info["is_recruit"] else "在职"
        print(f"  {person}({person_info['position']}, {status}): {workload:.2f}")
        project_total += workload
    print(f"  项目总工作量: {project_total:.2f}")

print("\n\n人员总工作量汇总:")
print("-" * 80)
for person in people:
    total = person_total_workload[person["name"]]
    status = "待招" if person["is_recruit"] else "在职"
    print(f"{person['name']}({person['position']}, {status}): {total:.2f}")

print("\n\nExcel表格填充建议:")
print("=" * 80)
for proj in projects:
    for person, workload in assignment[proj].items():
        if workload > 0.001:
            print(f"{proj[:20]:<20} | {person:<10} | {workload:.2f}")

if all_valid:
    print("\n🎉 所有约束条件都已满足!")
else:
    print("\n⚠️  存在未满足的约束条件，需要进行手动调整")