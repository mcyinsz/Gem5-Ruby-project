import math
from m5.objects import *

class All2AllNetwork(GarnetNetwork):

    def __init__(self, ruby_system, flit_size: int = 4):
        super().__init__()
        self.ruby_system = ruby_system

        # set network bandwidth and latency parameters
        self.ni_flit_size = flit_size
        self.ext_links = []
        self.int_links = []
        self.routers = []
        self.netifs = []

    def connectControllers(self, controllers, hop_latency: int = 1):
        num_controllers = len(controllers)

        # create routers
        self.routers = [
            GarnetRouter(router_id=i) for i in range(num_controllers)
        ]

        # set router params
        for router in self.routers:
            router.latency = hop_latency

        # create network interface
        self.netifs = [
            GarnetNetworkInterface(id=i) for i in range(num_controllers)
        ]

        # create external link and set params
        for i in range(num_controllers):
            ext_link = GarnetExtLink(
                link_id=i,
                ext_node=controllers[i],
                int_node=self.routers[i],
            )
            ext_link.latency = hop_latency # cycle
            self.ext_links.append(ext_link)

        # inner links
        link_id = 0
        for i in range(num_controllers):
            for j in range(i + 1, num_controllers):
                # create bidirectional links
                int_link1 = GarnetIntLink(
                    link_id=link_id,
                    src_node=self.routers[i],
                    dst_node=self.routers[j],
                    src_outport="OutPort_%d_to_%d" % (i, j),
                    dst_inport="InPort_%d_to_%d" % (i, j),
                )
                int_link1.latency = hop_latency

                int_link2 = GarnetIntLink(
                    link_id=link_id + 1,
                    src_node=self.routers[j],
                    dst_node=self.routers[i],
                    src_outport="OutPort_%d_to_%d" % (j, i),
                    dst_inport="InPort_%d_to_%d" % (j, i),
                )
                int_link2.latency = hop_latency

                self.int_links.extend([int_link1, int_link2])
                link_id += 2
