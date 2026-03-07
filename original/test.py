if count == 1:
    direction = None  # 选出可通行路径
    for dtion in path:
        if path[dtion]:
            direction = dtion
    move_forword = direction  # 重新进行循环，行动并排除走过的路
    break  # 退出这个循环
elif count > 1:  # 如果多于一条路
    direction = []  # 选出可通行路径
    for dtion in path:
        if path[dtion]:
            direction.append(dtion)  # 第一个可以走的路
            if max_drones() == num_drones():  # 如果无人机位置满了并运行到这里就自杀
                return
            # 如果可以召唤则开始，没有则等待
            while True:
                if max_drones() - num_drones() > 0:
                    if dtion == West:  # 召唤无人机(因为无法传参只能这样)
                        spawn_drone(pathfinding_west)
                    elif dtion == South:
                        spawn_drone(pathfinding_south)
                    elif dtion == East:
                        spawn_drone(pathfinding_east)
                    elif dtion == North:
                        spawn_drone(pathfinding_north)
                    break