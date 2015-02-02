import json
import argparse
import logging
import sys

from dock import build_image_here, build_image_in_privileged_container, \
    build_image_using_hosts_docker, set_logging
from dock.constants import CONTAINER_BUILD_JSON_PATH, CONTAINER_RESULTS_JSON_PATH
from dock.buildimage import BuildImageBuilder
from dock.inner import BuildResultsEncoder, build_inside, BuildResults


logger = logging.getLogger('dock')


def cli_create_build_image(args):
    b = BuildImageBuilder(dock_tarball_path=args.dock_tarball_path,
                          dock_local_path=args.dock_local_path,
                          dock_remote_path=args.dock_remote_git,
                          use_official_dock_git=args.dock_latest)
    try:
        b.create_image(args.dockerfile_dir_path, args.image, use_cache=args.use_cache)
    except RuntimeError:
        logger.error("Build failed.")
        sys.exit(1)


def cli_build_image(args):
    if args.json:
        with open(args.json) as json_fp:
            common_kwargs = json.load(json_fp)
    else:
        common_kwargs = {
            "git_url": args.git_url,
            "image": args.image,
            "git_dockerfile_path": args.git_path,
            "git_commit": args.git_commit,
            "parent_registry": args.source_registry,
            "target_registries": args.target_registries,
        }
    response = BuildResults()
    if args.method == "hostdocker":
        response = build_image_using_hosts_docker(args.build_image, **common_kwargs)
    elif args.method == "privileged":
        response = build_image_in_privileged_container(args.build_image, **common_kwargs)
    elif args.method == 'here':
        image = build_image_here(**common_kwargs)
        if not image:
            response.return_code = -1
        else:
            response.return_code = 0
    sys.exit(response.return_code)


def cli_inside_build(args):
    build_inside(input=args.input, input_args=args.input_arg)


def store_result(results):
    # TODO: move this to api, it shouldnt be part of CLI
    with open(CONTAINER_RESULTS_JSON_PATH, 'w') as results_json_fd:
        json.dump(results, results_json_fd, cls=BuildResultsEncoder)


class CLI(object):
    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description="dock, tool for building images"
        )

    def set_arguments(self):
        exclusive_group = self.parser.add_mutually_exclusive_group()
        exclusive_group.add_argument("-v", "--verbose", action="store_true")
        exclusive_group.add_argument("-q", "--quiet", action="store_true")

        subparsers = self.parser.add_subparsers(help='commands')

        # BUILDING IMAGES

        build_parser = subparsers.add_parser('build', help='build image')
        build_parser.set_defaults(func=cli_build_image)
        build_parser.add_argument("--json", action="store", help="path to build json")
        build_parser.add_argument("--build-image", action='store', help="name of build image to use "
                                  "(build image type has to match method)")
        build_parser.add_argument("--image", action='store', help="name under the image will be accessible")
        build_parser.add_argument("--git-url", action='store', metavar="URL", help="URL to git repo")
        build_parser.add_argument("--git-path", action='store',
                                  help="path to Dockerfile within git repo (default is ./)")
        build_parser.add_argument("--git-commit", action='store',
                                  help="checkout this commit (default is master)")
        build_parser.add_argument("--source-registry", action='store',
                                  metavar="REGISTRY",
                                  help="registry to pull base image from")
        build_parser.add_argument("--target-registries", action='store', nargs="*",
                                  metavar="REGISTRY",
                                  help="list of registries to push image to")
        build_parser.add_argument("--method", action='store', choices=["hostdocker", "privileged", "here"],
                                  help="choose method for building image: 'hostdocker' mounts socket "
                                       "inside container, 'privileged' spawns privileged container and "
                                       "runs separate docker instance inside and finally 'here' executes"
                                       "build in current environment")

        # CREATE BUILD IMAGE

        bi_parser = subparsers.add_parser('create-build-image',
                                          help='create build image where images are being build')
        bi_parser.set_defaults(func=cli_create_build_image)
        dock_source = bi_parser.add_mutually_exclusive_group()
        dock_source.add_argument("--dock-latest", action='store_true',
                                 help="put latest dock inside (from public git)")
        dock_source.add_argument("--dock-remote-git", action='store',
                                 help="URL to git repo with dock (has to contain setup.py)")
        dock_source.add_argument("--dock-local-path", action='store',
                                 help="path to directory with dock (has to contain setup.py)")
        dock_source.add_argument("--dock-tarball-path", action='store',
                                 help="path to distribution tarball with dock")
        bi_parser.add_argument("dockerfile_dir_path", action="store", metavar="DOCKERFILE_DIR_PATH",
                               help="path to directory with Dockerfile")
        bi_parser.add_argument("image", action='store', metavar="IMAGE",
                               help="name under the image will be accessible")
        bi_parser.add_argument("--use-cache", action='store_true', default="store_false",
                               help="use cache to build image (may be faster, but not up to date)")

        # inside build
        ib_parser = subparsers.add_parser(
            'inside-build',
            help="we do expect we are inside container, therefore we'll read "
                 "build configuration from json at '%s' and when the build is done, " % CONTAINER_BUILD_JSON_PATH +
                 "results are written in that dir so dock from host may read those")
        ib_parser.add_argument("--input", action='store', help="input plugin name")
        ib_parser.add_argument("--input-arg", action='append',
                               help="argument for input plugin (in form of 'key=value'), see input plugins "
                                    " to know what arguments they accept (can be specified multiple times)")
        ib_parser.set_defaults(func=cli_inside_build)

    def run(self):
        self.set_arguments()
        args = self.parser.parse_args()
        if args.verbose:
            set_logging(logging.DEBUG)
        elif args.quiet:
            set_logging(logging.WARNING)
        else:
            set_logging(logging.INFO)
        try:
            args.func(args)
        except AttributeError:
            self.parser.print_help()
        except KeyboardInterrupt:
            pass
        except Exception as ex:
            if args.verbose:
                raise
            else:
                logger.error("Exception caught: %s", repr(ex))


def run():
    cli = CLI()
    cli.run()


if __name__ == '__main__':
    run()
