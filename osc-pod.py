import os
import platform
import getpass
import tempfile

from osc import cmdln
from osc import core
from osc import oscerr


class SimpleProgress:
    """
    Class with the same API as tqdm to use when the module is not
    installed
    """
    def __init__(self, iterable):
        self._iterable = iterable
        self._size = len(self._iterable)
        self._index = 0

    def __iter__(self):
        return self._iterable.__iter__()

    def set_description(self, desc):
        self._index += 1
        p = (self._index / self._size) * 100
        print(f'\r{desc} {p:.2f}% {self._index}/{self._size}', end='')


try:
    from tqdm import tqdm
except ModuleNotFoundError:
    tqdm = SimpleProgress


repo2image = {
    'openSUSE_Factory': 'opensuse/tumbleweed',
    'openSUSE_Tumbleweed': 'opensuse/tumbleweed',
}

arch2arch = {
    'x86_64': 'amd64'
}

def get_buildroot(apihost, project, package, repo, arch, vm_type, user=None):
    user = user or ""
    dash_user = f"-{user:s}" if user else ""
    buildroot = core.conf.config["build-root"] % {
        'apihost': apihost,
        'project': project,
        'package': package,
        'repo': repo,
        'arch': arch,
        "user": user,
        "dash_user": dash_user,
    }

    # Taken from osc/build.py
    if vm_type != 'lxc' and vm_type != 'nspawn':
        buildroot = os.path.join(buildroot, '.mount')

    return buildroot

def get_pacdir(buildroot:str, arch: str) -> str:
    pacdir = os.path.join(buildroot, '.build.packages')
    if os.path.islink(pacdir):
        pacdir = os.readlink(pacdir)
        pacdir = os.path.join(buildroot, pacdir)

    return os.path.join(pacdir, 'RPMS', arch)

def store_read_last_buildroot() -> list[str]:
    last_broot = core.store_read_last_buildroot('.')

    if last_broot:
        return last_broot
    else:
        raise oscerr.OscBaseError("Could not find package buildroot")


@cmdln.option('-w', '--workdir', action='store_true',
              help='use volume as the work dir')
@cmdln.option('-r', '--runner', default='podman',
              help='use the specified runner')
@cmdln.option('-v', '--volume', default='/root/rpms',
              help='overwride rpms mount point')
@cmdln.option('-p', '--platform', default='',
              help='use the specified platformstring, i.e., linux/amd64')
@cmdln.option('-b', '--get-binaries', action='store_true',
              help='download binaries from obs')
@cmdln.option('--repo',
              help='Use this repo to download binaries')
def do_pod(self, subcmd, opts, *args):
    """${cmd_name}: Run a container with the build rpms

    Examples:
        osc pod IMAGE   # Run the containr with the IMAGE
                          (default behaviour is to guess
                           the image based on the repo)

    """
    verbose = opts.verbose
    debug = opts.debug

    image: str = ''
    target: str = ''
    entrypoint: str = ''

    native_arch = platform.processor()

    try:
        package = core.store_read_package('.')
    except oscerr.NoWorkingCopy as e:
        package = None
    project = core.store_read_project('.')

    try:
        repo, arch, runner = store_read_last_buildroot()
    except oscerr.OscBaseError as e:
        # XXX: Maybe we should query osc for repos and prompt the user to
        #      choose one. Also set get_binaries
        repo, arch, runner = 'openSUSE_Factory', native_arch, ''

    if opts.repo:
        repo = opts.repo

    if args and len(args) > 1:
        raise oscerr.WrongArgs("Too many images!")
    elif args:
        image = args[0];
    else:
        # FIXME:
        image = repo2image[repo]

    user = getpass.getuser() if runner in ['podman', 'kvm', 'qemu'] else None

    if opts.get_binaries:
        # Download packages from osc
        apiurl = self.get_api_url()
        binaries = core.get_binarylist(apiurl, project, repo, arch, package)

        bindir = tempfile.TemporaryDirectory()
        pacdir = bindir.name
        print(f'Downloading {len(binaries)} binaries from {project}/{package or ""} {arch}')
        binaries = tqdm(binaries)
        for b in binaries:
            binaries.set_description(f'{b[:30]:<30}')
            core.get_binary_file(apiurl, project, repo, arch, b, package,
                                 target_filename=f'{pacdir}/{b}')
    else:
        buildroot = get_buildroot('', project, package,
                                  repo, arch, runner, user)
        pacdir = get_pacdir(buildroot, arch)

    # Skip pasing `--platform` if the last build was the same target as us,
    # this makes podman start faster
    if platform.processor() != arch:
        target = f"--platform linux/{arch2arch[arch]}"
    elif opts.platform:
        target = f"--platform {opts.platform}"

    runner = opts.runner
    volume = opts.volume

    if opts.workdir:
        entrypoint = f'-w {volume}'

    if verbose:
        print(f'Running {runner} image {image} with {project}/{package} rpms in {volume}')

    cmd = (f'{runner} run --rm -it -v={pacdir}:{volume}:z {target} {entrypoint} {image}')

    if debug:
        print(cmd)

    os.system(cmd)
