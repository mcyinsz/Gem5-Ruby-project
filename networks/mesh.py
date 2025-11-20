import math
from m5.objects import *

class MeshNetwork(GarnetNetwork):

    def __init__(
        self, 
        ruby_system,
        flit_size: int = 4
    ):
        super().__init__()
        self.ruby_system = ruby_system
        self.ni_flit_size = flit_size

    def connectControllers(
        self, 
        controllers,
        hop_latency: int = 1
    ):
        num_controllers = len(controllers)
        
        # 1. determine the row number and column number of the mesh
        rows = int(math.sqrt(num_controllers))
        cols = int(math.ceil(num_controllers / rows))
        
        # 2. assure that the node number can cover the cpu number
        while rows * cols < num_controllers:
            cols += 1

        print(f"Creating {rows}x{cols} Mesh topology for {num_controllers} controllers")

        # 3. create routers
        self.routers = []
        router_id = 0
        for i in range(rows):
            for j in range(cols):
                if router_id < num_controllers:
                    router = GarnetRouter(router_id=router_id)
                    router.latency = hop_latency
                    self.routers.append(router)
                    router_id += 1

        # 4. create network interface
        self.netifs = [
            GarnetNetworkInterface(id=i) for i in range(num_controllers)
        ]

        # 5. create external links
        self.ext_links = []
        for i in range(num_controllers):
            ext_link = GarnetExtLink(
                link_id=i,
                ext_node=controllers[i],
                int_node=self.routers[i],
            )
            ext_link.bandwidth_factor = 1
            ext_link.latency = 1
            self.ext_links.append(ext_link)

        # 6. create internal links
        self.int_links = []
        link_id = 0

        # 7. link the routers with coordinators
        for i in range(rows):
            for j in range(cols):
                current_idx = i * cols + j
                if current_idx >= num_controllers:
                    continue

                # east neighbor
                if j < cols - 1:
                    east_idx = i * cols + (j + 1)
                    if east_idx < num_controllers:
                        int_link_east = GarnetIntLink(
                            link_id=link_id,
                            src_node=self.routers[current_idx],
                            dst_node=self.routers[east_idx],
                            src_outport="East",
                            dst_inport="West",
                        )
                        int_link_east.bandwidth_factor = 1
                        int_link_east.latency = 1
                        self.int_links.append(int_link_east)
                        link_id += 1

                        # west neighbor
                        int_link_west = GarnetIntLink(
                            link_id=link_id,
                            src_node=self.routers[east_idx],
                            dst_node=self.routers[current_idx],
                            src_outport="West",
                            dst_inport="East",
                        )
                        int_link_west.bandwidth_factor = 1
                        int_link_west.latency = 1
                        self.int_links.append(int_link_west)
                        link_id += 1

                # south neighbor
                if i < rows - 1:
                    south_idx = (i + 1) * cols + j
                    if south_idx < num_controllers:
                        # south -> north
                        int_link_south = GarnetIntLink(
                            link_id=link_id,
                            src_node=self.routers[current_idx],
                            dst_node=self.routers[south_idx],
                            src_outport="South",
                            dst_inport="North",
                        )
                        int_link_south.bandwidth_factor = 1
                        int_link_south.latency = 1
                        self.int_links.append(int_link_south)
                        link_id += 1

                        # north -> south
                        int_link_north = GarnetIntLink(
                            link_id=link_id,
                            src_node=self.routers[south_idx],
                            dst_node=self.routers[current_idx],
                            src_outport="North",
                            dst_inport="South",
                        )
                        int_link_north.bandwidth_factor = 1
                        int_link_north.latency = 1
                        self.int_links.append(int_link_north)
                        link_id += 1