#!/usr/bin/env python

import pyrax
import os
import argparse
import time
import paramiko
import getpass


def create_server(credential_file=None, username=None, api_key=None,
                  image=None, flavor=None, server_name=None,
                  server_name_prefix=None):
    """Create a Server."""

    if not (username or api_key or credential_file):
        raise ValueError("No credentials specified")
    if credential_file and (username or api_key):
        raise ValueError("Conflicting credential options specified.")
    if api_key and not username:
        raise ValueError("No username specified")
    if username and not api_key:
        raise ValueError("No API key specified")

    # TODO: get credentials from command line
    if credential_file:
        pyrax.set_credential_file(credential_file)
    else:
        pyrax.set_credentials(username=username, api_key=api_key)

    cs = pyrax.cloudservers

    if image is None:
        image = [img for img in cs.images.list()
                 if "CentOS 6.3" in img.name][0]
    if flavor is None:
        flavor = [fl for fl in cs.flavors.list() if fl.ram == 1024][0]

    if server_name is None:
        t = time.localtime()
        date_string = '%d-%02d-%02d-%02d-%02d-%02d' % (t.tm_year, t.tm_mon,
                                                       t.tm_mday, t.tm_hour,
                                                       t.tm_min, t.tm_sec)
        whoami = getpass.getuser()
        if server_name_prefix is None:
            server_name_prefix = 'repose'
        server_name = '%s-%s-%s' % (server_name_prefix, date_string, whoami)

    server = cs.servers.create(name=server_name,
                               image=image, flavor=flavor)

    print time.asctime()
    n = 0
    while n < 600:
        server2 = cs.servers.get(server.id)
        if server2.status == u'ACTIVE':
            break
        if server2.status != u'BUILD' and server2.status != u'UNKNOWN':
            raise Exception("Server entered an invalid state: '%s'" %
                            server.status)
        time.sleep(15)
        print time.asctime()
        n += 15

    if server2.status != u'ACTIVE':
        raise Exception('Server failed to build in time')

    server2.adminPass = server.adminPass
    return server2


def add_server_to_known_hosts_file(server):
    ips = server.networks['public']
    os.system('ssh-keyscan %s 2>/dev/null >> ~/.ssh/known_hosts' %
              ' '.join(ips))


def install_prereqs(server):
    username = 'root'
    password = server.adminPass
    print 'password: %s' % password
    ips = server.networks['public']

    ssh_client = paramiko.SSHClient()
    ssh_client.load_system_host_keys()

    connected = False

    for ip in ips:
        try:
            ssh_client.connect(hostname=ip, username=username,
                               password=password)
            connected = True
            break
        except:
            pass

    if not connected:
        raise Exception("Could not connect")

    def readfile(file):
        try:
            return file.read()
        except:
            return None

    def exec_command2(command, bufsize=-1):
        return map(readfile, ssh_client.exec_command(command, bufsize))

    epel_filename = 'epel-release-6-8.noarch.rpm'
    epel_url = ('http://download.fedoraproject.org/pub/epel/6/i386/%s' %
                epel_filename)

    stdio = exec_command2('wget %s' % epel_url)
    stdio = exec_command2('rpm -Uvh %s' % epel_filename)
    stdio = exec_command2('rm -f %s' % epel_filename)

    stdio = exec_command2('yum install -y python python-pip git')

    stdio = exec_command2('pip-python install virtualenv')


def run():
    parser = argparse.ArgumentParser(description="Create a server and install "
                                     "Repose on it.")
    parser.add_argument('--credential-file',
                        help="Specify credentials to use to authenticate to "
                        "the compute service")
    parser.add_argument('--username')
    parser.add_argument('--api-key')
    parser.add_argument('--image')
    parser.add_argument('--flavor')
    parser.add_argument('--name-prefix')

    args = parser.parse_args()

    if args.credential_file and (args.username or args.api_key):
        raise ValueError("Conflicting credential options specified.")
    if args.api_key and not args.username:
        raise ValueError("No username specified")
    if not (args.username or args.api_key or args.credential_file):
        raise ValueError("No credentials specified")
    if args.username and not args.api_key:
        raise ValueError("No API key specified")

    server = create_server(credential_file=args.credential_file,
                           username=args.username, api_key=args.api_key,
                           image=args.image, flavor=args.flavor,
                           server_name_prefix=args.name_prefix)
    add_server_to_known_hosts_file(server)
    install_prereqs(server)


if __name__ == '__main__':
    run()
