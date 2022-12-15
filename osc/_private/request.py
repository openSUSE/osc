from . import package as osc_package


def forward_request(apiurl, request, interactive=True):
    """
    Forward the specified `request` to the projects the packages were branched from.
    """
    from .. import core as osc_core

    for action in request.get_actions("submit"):
        package = osc_package.ApiPackage(apiurl, action.tgt_project, action.tgt_package)

        if not package.linkinfo:
            # not a linked/branched package, can't forward to parent
            continue

        project = package.linkinfo.project
        package = package.linkinfo.package

        if interactive:
            reply = input(f"\nForward request to {project}/{package}? ([y]/n) ")
            if reply.lower() not in ("y", ""):
                continue

        msg = f"Forwarded request #{request.reqid} from {request.creator}\n\n{request.description}"
        new_request_id = osc_core.create_submit_request(
            apiurl,
            action.tgt_project,
            action.tgt_package,
            project,
            package,
            msg,
        )
        msg = f"Forwarded request #{request.reqid} from {request.creator} to {project}/{package}: #{new_request_id}"
        print(msg)
