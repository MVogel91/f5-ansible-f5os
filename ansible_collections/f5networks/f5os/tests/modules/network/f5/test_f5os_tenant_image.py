# -*- coding: utf-8 -*-
#
# Copyright: (c) 2022, F5 Networks Inc.
# GNU General Public License v3.0 (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

import json
import os

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.f5networks.f5os.plugins.modules.f5os_tenant_image import (
    ModuleParameters, ArgumentSpec, ModuleManager
)
from ansible_collections.f5networks.f5os.plugins.module_utils.common import F5ModuleError

from ansible_collections.f5networks.f5os.tests.compat import unittest
from ansible_collections.f5networks.f5os.tests.compat.mock import Mock, patch
from ansible_collections.f5networks.f5os.tests.modules.utils import set_module_args


fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures')
fixture_data = {}


def load_fixture(name):
    path = os.path.join(fixture_path, name)

    if path in fixture_data:
        return fixture_data[path]

    with open(path) as f:
        data = f.read()

    try:
        data = json.loads(data)
    except Exception:
        pass

    fixture_data[path] = data
    return data


class TestParameters(unittest.TestCase):
    def test_module_parameters(self):
        args = dict(
            image_name='BIGIP-bigip.ALL-VELOS.qcow2.zip',
            remote_host='1.2.3.4',
            remote_user='admin',
            remote_password='admin',
            remote_path='/test/',
            protocol='https',
            local_path='images',
            state='present',
            timeout=600
        )

        p = ModuleParameters(params=args)
        assert p.image_name == 'BIGIP-bigip.ALL-VELOS.qcow2.zip'
        assert p.remote_host == '1.2.3.4'
        assert p.remote_user == 'admin'
        assert p.remote_password == 'admin'
        assert p.remote_path == '/test/BIGIP-bigip.ALL-VELOS.qcow2.zip'
        assert p.local_path == 'images'
        assert p.protocol == 'https'
        assert p.state == 'present'
        assert p.timeout == (6.0, 100)


class TestManager(unittest.TestCase):
    def setUp(self):
        self.spec = ArgumentSpec()
        self.p1 = patch('ansible_collections.f5networks.f5os.plugins.modules.f5os_tenant_image.F5Client')
        self.p2 = patch('time.sleep')
        self.p2.start()
        self.m1 = self.p1.start()
        self.m1.return_value = Mock()
        self.p3 = patch('ansible_collections.f5networks.f5os.plugins.modules.f5os_tenant_image.send_teem')
        self.m3 = self.p3.start()
        self.m3.return_value = True

    def tearDown(self):
        self.p1.stop()
        self.p2.stop()
        self.p3.stop()

    def test_import_image(self, *args):
        set_module_args(dict(
            image_name='BIGIP-bigip14.1.x-miro-14.1.2.5-0.0.336.ALL-VELOS.qcow2.zip',
            remote_host='fake.imageserver.foo.bar.com',
            remote_user='admin',
            local_path='images',
            remote_password='admin',
            remote_path='/test/',
            state='import',
        ))

        module = AnsibleModule(
            argument_spec=self.spec.argument_spec,
            supports_check_mode=self.spec.supports_check_mode,
            required_if=self.spec.required_if
        )
        expected = {'input': [{'protocol': 'scp', 'remote-host': 'fake.imageserver.foo.bar.com',
                               'remote-file': '/test/BIGIP-bigip14.1.x-miro-14.1.2.5-0.0.336.ALL-VELOS.qcow2.zip',
                               'username': 'admin', 'password': 'admin', 'local-file': 'images', 'insecure': ''}]
                    }
        # Override methods to force specific logic in the module to happen
        mm = ModuleManager(module=module)
        mm.client.platform = 'rSeries Platform'
        mm.exists = Mock(return_value=False)
        mm.client.post = Mock(return_value=dict(code=200, contents=dict(load_fixture('start_image_import.json'))))

        results = mm.exec_module()
        assert results['changed'] is True
        assert mm.client.post.call_args[1]['data'] == expected
        assert results['image_name'] == 'BIGIP-bigip14.1.x-miro-14.1.2.5-0.0.336.ALL-VELOS.qcow2.zip'
        assert results['remote_path'] == '/test/BIGIP-bigip14.1.x-miro-14.1.2.5-0.0.336.ALL-VELOS.qcow2.zip'
        assert results['message'] == "Image BIGIP-bigip14.1.x-miro-14.1.2.5-0.0.336.ALL-VELOS.qcow2.zip import started."

    def test_import_image_progress_check(self, *args):
        set_module_args(dict(
            image_name='BIGIP-bigip14.1.x-miro-14.1.2.5-0.0.336.ALL-VELOS.qcow2.zip',
            remote_host='fake.imageserver.foo.bar.com',
            local_path='images',
            remote_path='/test/',
            state='present',
        ))

        module = AnsibleModule(
            argument_spec=self.spec.argument_spec,
            supports_check_mode=self.spec.supports_check_mode,
            required_if=self.spec.required_if
        )
        progress_82 = dict(code=200, contents=load_fixture('f5os_tenant_image_upload_progress.json'))
        complete = dict(code=200, contents=load_fixture('f5os_tenant_image_upload_complete.json'))
        replicated = dict(code=200, contents={"f5-tenant-images:status": "replicated"})

        mm = ModuleManager(module=module)
        mm.client.platform = 'rSeries Platform'
        mm.exists = Mock(return_value=False)
        mm.client.get = Mock(side_effect=[progress_82, complete, replicated])
        results = mm.exec_module()

        assert results['changed'] is True
        assert results['message'] == 'Image BIGIP-bigip14.1.x-miro-14.1.2.5-0.0.336.ALL-VELOS.qcow2.zip ' \
                                     'import successful.'
        assert mm.client.get.call_count == 3

    def test_image_imported_failed_verification(self):
        set_module_args(dict(
            image_name='BIGIP-bigip14.1.x-miro-14.1.2.5-0.0.336.ALL-VELOS.qcow2.zip',
            remote_host='fake.imageserver.foo.bar.com',
            local_path='images',
            remote_path='/test/',
            state='present',
        ))

        module = AnsibleModule(
            argument_spec=self.spec.argument_spec,
            supports_check_mode=self.spec.supports_check_mode,
            required_if=self.spec.required_if
        )
        msg = 'The image: BIGIP-bigip14.1.x-miro-14.1.2.5-0.0.336.ALL-VELOS.qcow2.zip was imported, ' \
              'but it failed signature verification, remove the image and try again.'
        complete = dict(code=200, contents=load_fixture('f5os_tenant_image_upload_complete.json'))
        importing = dict(code=200, contents={"f5-tenant-images:status": "importing"})
        verifying = dict(code=200, contents={"f5-tenant-images:status": "verifying"})
        failed = dict(code=200, contents={"f5-tenant-images:status": "verification-failed"})

        mm = ModuleManager(module=module)
        mm.client.platform = 'rSeries Platform'
        mm.exists = Mock(return_value=False)
        mm.client.get = Mock(side_effect=[complete, importing, complete, verifying, complete, failed])

        with self.assertRaises(F5ModuleError) as err:
            mm.exec_module()

        assert msg in str(err.exception)
        assert mm.client.get.call_count == 6

    def test_remove_image(self):
        set_module_args(dict(
            image_name='BIGIP-bigip14.1.x-miro-14.1.2.5-0.0.336.ALL-VELOS.qcow2.zip',
            state='absent',
        ))

        module = AnsibleModule(
            argument_spec=self.spec.argument_spec,
            supports_check_mode=self.spec.supports_check_mode,
            required_if=self.spec.required_if
        )

        response = dict(code=200, contents={"f5-tenant-images:output": {"result": "Successful."}})
        mm = ModuleManager(module=module)
        mm.client.platform = 'rSeries Platform'
        mm.exists = Mock(side_effect=[True, False])
        mm.client.post = Mock(return_value=response)

        results = mm.exec_module()

        assert results['changed'] is True

    def test_image_import_failed(self):
        set_module_args(dict(
            image_name='BIGIP-bigip14.1.x-miro-14.1.2.5-0.0.336.ALL-VELOS.qcow2.zip',
            remote_host='fake.imageserver.foo.bar.com',
            remote_user='admin',
            remote_password='admin',
            remote_path='/test/',
            local_path='images',
            state='import',
        ))

        module = AnsibleModule(
            argument_spec=self.spec.argument_spec,
            supports_check_mode=self.spec.supports_check_mode,
            required_if=self.spec.required_if
        )

        mm = ModuleManager(module=module)
        mm.client.platform = 'rSeries Platform'
        mm.exists = Mock(return_value=False)
        mm.client.post = Mock(return_value=dict(code=400, contents={'operation failed'}))

        with self.assertRaises(F5ModuleError):
            mm.exec_module()

    def test_remove_image_failed(self):
        set_module_args(dict(
            image_name='BIGIP-bigip14.1.x-miro-14.1.2.5-0.0.336.ALL-VELOS.qcow2.zip',
            state='absent',
        ))

        module = AnsibleModule(
            argument_spec=self.spec.argument_spec,
            supports_check_mode=self.spec.supports_check_mode,
            required_if=self.spec.required_if
        )

        response = dict(code=200, contents={"f5-tenant-images:output": {"result": "Failed."}})
        mm = ModuleManager(module=module)
        mm.client.platform = 'rSeries Platform'
        mm.exists = Mock(return_value=True)
        mm.client.post = Mock(return_value=response)

        with self.assertRaises(F5ModuleError) as err:
            mm.exec_module()
        assert 'Failed to remove tenant image: ' \
               'BIGIP-bigip14.1.x-miro-14.1.2.5-0.0.336.ALL-VELOS.qcow2.zip Failed.' in str(err.exception)

    def test_upload_image_failed(self):
        set_module_args(dict(
            image_name='BIGIP-bigip14.1.x-miro-14.1.2.5-0.0.336.ALL-VELOS.qcow2.zip',
            remote_host='fake.imageserver.foo.bar.com',
            remote_path='/test/',
            local_path='images',
            state='present',
        ))

        module = AnsibleModule(
            argument_spec=self.spec.argument_spec,
            supports_check_mode=self.spec.supports_check_mode,
            required_if=self.spec.required_if
        )

        mm = ModuleManager(module=module)
        mm.client.platform = 'rSeries Platform'
        mm.exists = Mock(return_value=False)
        mm.client.get = Mock(return_value=dict(code=200, contents=load_fixture('f5os_tenant_image_upload_failed.json')))

        with self.assertRaises(F5ModuleError) as err:
            mm.exec_module()
        assert 'File upload failed with the following result: ' \
               'Peer certificate cannot be authenticated with given CA certificates' == str(err.exception)

    def test_upload_image_did_not_start(self):
        set_module_args(dict(
            image_name='foobar.iso',
            remote_host='fake.foo.bar.com',
            remote_path='/test/',
            local_path='images',
            state='present',
        ))

        module = AnsibleModule(
            argument_spec=self.spec.argument_spec,
            supports_check_mode=self.spec.supports_check_mode,
            required_if=self.spec.required_if
        )

        mm = ModuleManager(module=module)
        mm.client.platform = 'rSeries Platform'
        mm.exists = Mock(return_value=False)
        mm.client.get = Mock(return_value=dict(
            code=200, contents=load_fixture('f5os_tenant_image_upload_complete.json'))
        )
        with self.assertRaises(F5ModuleError) as err:
            mm.exec_module()
        assert 'File upload job not has not started, check device logs for more information.' == str(err.exception)

    def test_velos_controller_raises(self, *args):
        set_module_args(dict(
            image_name='BIGIP-bigip14.1.x-miro-14.1.2.5-0.0.336.ALL-VELOS.qcow2.zip',
            state='absent',
        ))

        module = AnsibleModule(
            argument_spec=self.spec.argument_spec,
            supports_check_mode=self.spec.supports_check_mode,
        )

        mm = ModuleManager(module=module)
        mm.is_velos_controller = Mock(return_value=True)
        mm.client.platform = 'Velos Controller'

        with self.assertRaises(F5ModuleError) as err:
            mm.exec_module()

        assert 'Target device is a VELOS controller, aborting.' in str(err.exception)
