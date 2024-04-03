def get_npm_tarball(npm_post_data):
    attachments = npm_post_data.get('_attachments', {})
    # TODO: can there be multiple attachments?
    if not attachments:
        return None
    tarball = list(attachments.values())[0].get('data')
    if not tarball:
        return None
    return tarball
