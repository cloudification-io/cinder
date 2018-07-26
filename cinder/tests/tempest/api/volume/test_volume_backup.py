# Copyright (c) 2016 Mirantis Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_config import cfg
import testtools

from tempest.common import waiters
from tempest import config
from tempest.lib.common.utils import data_utils
from tempest import test

from cinder.tests.tempest.api.volume import base


# TODO(obutenko): Remove this when liberty-eol happens.
snapshot_backup_opt = cfg.BoolOpt('snapshot_backup',
                                  default=False,
                                  help='Creating backup from snapshot not '
                                  'implemented in Liberty.')

CONF = config.CONF
CONF.register_opt(snapshot_backup_opt, group='volume-feature-enabled')


class VolumesBackupsTest(base.BaseVolumeTest):

    @classmethod
    def skip_checks(cls):
        super(VolumesBackupsTest, cls).skip_checks()
        if not CONF.volume_feature_enabled.backup:
            raise cls.skipException("Cinder backup feature disabled")

    @testtools.skipUnless(CONF.volume_feature_enabled.snapshot_backup,
                          "Skip. Not implemented in Liberty.")
    @test.idempotent_id('885410c6-cd1d-452c-a409-7c32b7e0be15')
    def test_volume_snapshot_backup(self):
        """Create backup from snapshot."""
        volume = self.create_volume()
        # Create snapshot
        snapshot = self.create_snapshot(volume['id'])
        # Create backup
        backup = self.create_backup(
            volume_id=volume['id'],
            snapshot_id=snapshot['id'])
        self.assertEqual(volume['id'], backup['volume_id'])
        self.assertEqual(snapshot['id'], backup['snapshot_id'])

    @test.idempotent_id('b5d837b0-7066-455d-88fc-4a721a899306')
    def test_backup_create_and_restore_to_an_existing_volume(self):
        """Test backup create and restore to an existing volume."""
        # Create volume
        src_vol = self.create_volume()
        # Create backup
        backup = self.create_backup(volume_id=src_vol['id'])
        # Restore to existing volume
        restore = self.backups_client.restore_backup(
            backup_id=backup['id'],
            volume_id=src_vol['id'])['restore']
        waiters.wait_for_volume_resource_status(
            self.backups_client,
            backup['id'], 'available')
        waiters.wait_for_volume_resource_status(
            self.volumes_client,
            src_vol['id'], 'available')
        self.assertEqual(src_vol['id'], restore['volume_id'])
        self.assertEqual(backup['id'], restore['backup_id'])

    @test.idempotent_id('c810fe2c-cb40-43ab-96aa-471b74516a98')
    def test_incremental_backup(self):
        """Test create incremental backup."""
        # Create volume from image
        volume = self.create_volume(size=CONF.volume.volume_size,
                                    imageRef=CONF.compute.image_ref)

        # Create backup
        self.create_backup(volume_id=volume['id'])
        # Create a server
        bd_map = [{'volume_id': volume['id'],
                   'delete_on_termination': '0'}]

        server_name = data_utils.rand_name('instance')
        server = self.create_server(
            name=server_name,
            block_device_mapping=bd_map,
            wait_until='ACTIVE')

        # Delete VM
        self.os_primary.servers_client.delete_server(server['id'])
        # Create incremental backup
        waiters.wait_for_volume_resource_status(self.volumes_client,
                                                volume['id'], 'available')
        backup_incr = self.create_backup(
            volume_id=volume['id'],
            incremental=True)

        is_incremental = self.backups_client.show_backup(
            backup_incr['id'])['backup']['is_incremental']
        self.assertTrue(is_incremental)
