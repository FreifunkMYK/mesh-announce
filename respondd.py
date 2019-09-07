#!/usr/bin/env python3

import metasocketserver
import socketserver
import argparse
import socket
import struct
import json
import os
from zlib import compress

from providers import get_providers
import util

def get_handler(providers, batadv_ifaces, env):
    class ResponddUDPHandler(socketserver.BaseRequestHandler):
        def multi_request(self, providernames, local_env):
            ret = {}
            for name in providernames:
                try:
                    provider = providers[name]
                    ret[provider.name] = provider.call(local_env)
                except:
                    pass
            return compress(str.encode(json.dumps(ret)))[2:-4]

        def handle(self):
            data = self.request[0].decode('UTF-8').strip()
            socket = self.request[1]
            ifindex = self.request[2]

            batadv_dev = util.ifindex_to_batiface(ifindex, batadv_ifaces)
            if batadv_dev == None:
              return

            local_env = dict(env)
            local_env['batadv_dev'] = batadv_dev

            if data.startswith("GET "):
                response = self.multi_request(data.split(" ")[1:], local_env)
            else:
                answer = providers[data].call(local_env)
                if answer:
                    response = str.encode(json.dumps(answer))

            if response:
                socket.sendto(response, self.client_address)

    return ResponddUDPHandler

if __name__ == "__main__":
    parser = argparse.ArgumentParser(usage="""
      %(prog)s -h
      %(prog)s [-p <port>] [-g <group>] [-i [<group>%%]<if0>] [-i [<group>%%]<if1> ..] [-d <dir>] [-b <batman_iface>""")
    parser.add_argument('-p', dest='port',
                        default=1001, type=int, metavar='<port>',
                        help='port number to listen on (default 1001)')
    parser.add_argument('-g', dest='link_group',
                        default='ff02::2:1001', metavar='<link local group>',
                        help='link-local multicast group (default ff02::2:1001), set to emtpy string to disable')
    parser.add_argument('-s', dest='site_group',
                        default='ff05::2:1001', metavar='<site local group>',
                        help='site-local multicast group (default ff05::2:1001), set to empty string to disable')
    parser.add_argument('-i', dest='mcast_ifaces',
                        action='append', default=[ 'bat0' ], metavar='<iface>',
                        help='listening interface (default bat0), may be specified multiple times')
    parser.add_argument('-d', dest='directory',
                        default='./providers', metavar='<dir>',
                        help='data provider directory (default: $PWD/providers)')
    parser.add_argument('-b', dest='batadv_ifaces',
                        action='append', default=[ 'bat0' ], metavar='<iface>',
                        help='batman-adv interface to answer for (default: bat0). Specify once per domain')
    parser.add_argument('-m', dest='mesh_ipv4',
                        metavar='<mesh_ipv4>',
                        help='mesh ipv4 address')
    args = parser.parse_args()

    metasocketserver.MetadataUDPServer.address_family = socket.AF_INET6
    metasocketserver.MetadataUDPServer.allow_reuse_address = True
    server = metasocketserver.MetadataUDPServer(
        ("", args.port),
        get_handler(get_providers(args.directory), args.batadv_ifaces, {'mesh_ipv4': args.mesh_ipv4})
    )
    server.daemon_threads = True

    def join_group(mcast_group, if_index=0):
        group_bin = socket.inet_pton(socket.AF_INET6, mcast_group)
        mreq = group_bin + struct.pack('@I', if_index)
        server.socket.setsockopt(
            socket.IPPROTO_IPV6,
            socket.IPV6_JOIN_GROUP,
            mreq
        )

    mcast_iface_groups = { }
    for ifspec in args.mcast_ifaces:
        iface, *groups = reversed(ifspec.split('%'))
        if not iface in mcast_iface_groups:
            mcast_iface_groups[iface] = [ group for group in [ args.link_group, args.site_group ] if len(group) > 0 ]
        mcast_iface_groups[iface] += groups

    for (if_index, if_name) in socket.if_nameindex():
        if if_name in mcast_iface_groups:
            groups = mcast_iface_groups[if_name]
            for group in groups:
                join_group(group, if_index)

    server.serve_forever()
