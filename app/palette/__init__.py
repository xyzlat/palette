# FIXME: test if these are still needed and/or use absolute import
import monitor
import backup
import environment
import manage
import event
import yml
import request

from page import PalettePage

# Keep: this exposes to application.wsgi without a controller import
from controller.passwd import set_aes_key_file

class HomePage(PalettePage):
    TEMPLATE = 'dashboard.mako'
    active = 'home'


