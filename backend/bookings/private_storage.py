import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PassportStorage(FileSystemStorage):
    @property
    def base_location(self):
        return settings.PRIVATE_PASSPORT_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    def url(self, name):
        raise ValueError("Passport attachments are available only through authenticated downloads.")


passport_storage = PassportStorage()
