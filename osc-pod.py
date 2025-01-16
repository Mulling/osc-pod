import os
from osc import cmdln
from osc import core
from osc import oscerr


repo2image = {
    'openSUSE_Factory': 'opensuse/tumbleweed',
    'openSUSE_Tumbleweed': 'opensuse/tumbleweed',
}

@cmdln.option('-w', '--workdir', help='working directory', action='store_true')
@cmdln.option('-r', '--runner', default='podman',
              help='use the specified runner')
@cmdln.option('-v', '--volume', default='/root/rpms',
              help='overwride rpms mount point')
def do_pod(self, subcmd, opts, *args):
    """${cmd_name}: Run a container with the build rpms

    Examples:
        osc pod IMAGE   # Run the containr with the IMAGE
                          (default behaviour is to guess
                           the image based on the repo)

    """
    # TODO: Check if build_root is in the config and act accordingly
    # config_parse = core.conf.get_configParser(opts.conffile)
    # TODO: check for --vm-type=kvm|qemu
    # TODO: check if arch matches for the cases above

    repo: str = ""
    arch: str = ""
    image: str = ""
    entrypoint: str = ""

    pkg = core.store_read_package('.')

    last_broot = core.store_read_last_buildroot('.')

    if last_broot:
        repo, arch, _ = last_broot
    else:
        raise oscerr.OscBaseError("Could not find package buildroot")

    if args and len(args) > 1:
        raise oscerr.WrongArgs("Too many images!")
    elif args:
        image = args[0];
    else:
        # FIXME:
        image = repo2image[repo]

    build_root_dict = { 'dash_user': '', 'repo': repo, 'arch': arch, }
    build_root = core.conf.config.build_root % build_root_dict
    rpms = f'{build_root}/home/abuild/rpmbuild/RPMS/{arch}'

    runner = opts.runner
    volume = opts.volume

    if opts.workdir:
        entrypoint = f'-w {volume}'

    if opts.verbose:
        print(f'Running {runner} image {image} with {pkg} rpms in {volume}')

    os.system(f'{runner} run --rm -it -v={rpms}:{volume} {entrypoint} {image}')
