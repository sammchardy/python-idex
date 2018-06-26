from idex.exceptions import IdexWalletAddressNotFoundException, IdexPrivateKeyNotFoundException


def require_address(f):
    def check_address(self, *args, **kwargs):
        if not self._wallet_address:
            raise IdexWalletAddressNotFoundException()
        return f(self, *args, **kwargs)
    return check_address


def require_private_key(f):
    def check_private_key(self, *args, **kwargs):
        if not self._private_key:
            raise IdexPrivateKeyNotFoundException()
        return f(self, *args, **kwargs)
    return check_private_key
