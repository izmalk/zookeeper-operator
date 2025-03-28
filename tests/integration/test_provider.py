#!/usr/bin/env python3
# Copyright 2022 Canonical Ltd.
# See LICENSE file for licensing details.

import asyncio
import logging

import pytest
from pytest_operator.plugin import OpsTest

from .helpers import (
    check_acl_permission,
    check_jaas_config,
    get_application_hosts,
    get_password,
    get_relation_data,
    ping_servers,
)

logger = logging.getLogger(__name__)

APP_NAME = "zookeeper"
DUMMY_NAME_1 = "app"
DUMMY_NAME_2 = "appii"
REL_NAME = "zookeeper"


@pytest.mark.abort_on_fail
async def test_deploy_charms_relate_active(ops_test: OpsTest, zk_charm):
    app_charm = await ops_test.build_charm("tests/integration/app-charm")

    await asyncio.gather(
        ops_test.model.deploy(zk_charm, application_name=APP_NAME, num_units=3),
        ops_test.model.deploy(app_charm, application_name=DUMMY_NAME_1, num_units=1),
    )
    await ops_test.model.wait_for_idle(apps=[APP_NAME, DUMMY_NAME_1], timeout=1000)
    await ops_test.model.add_relation(APP_NAME, DUMMY_NAME_1)
    await ops_test.model.wait_for_idle(apps=[APP_NAME, DUMMY_NAME_1], timeout=1000)
    assert ops_test.model.applications[APP_NAME].status == "active"
    assert ops_test.model.applications[DUMMY_NAME_1].status == "active"
    assert ping_servers(ops_test)
    for unit in ops_test.model.applications[APP_NAME].units:
        jaas_config = check_jaas_config(model_full_name=ops_test.model_full_name, unit=unit.name)
        assert "sync" in jaas_config
        assert "super" in jaas_config
        # includes the related unit
        assert len(jaas_config) == 3

    assert len(ops_test.model.applications[DUMMY_NAME_1].units) == 1

    application_unit = ops_test.model.applications[DUMMY_NAME_1].units[0]
    # Get relation data
    relation_data = get_relation_data(
        model_full_name=ops_test.model_full_name, unit=application_unit.name, endpoint=REL_NAME
    )
    # Get the super password
    super_password = await get_password(ops_test=ops_test)
    units = [u.name for u in ops_test.model.applications[APP_NAME].units]
    # Get hosts where Zookeeper is deployed
    hosts = await get_application_hosts(ops_test=ops_test, app_name=APP_NAME, units=units)
    # Check acl permission for the application on each Zookeeper host
    for host in hosts:
        check_acl_permission(host, super_password, relation_data["database"])


@pytest.mark.abort_on_fail
async def test_deploy_multiple_charms_relate_active(ops_test: OpsTest):
    app_charm = await ops_test.build_charm("tests/integration/app-charm")

    await ops_test.model.deploy(app_charm, application_name=DUMMY_NAME_2, num_units=1)
    await ops_test.model.wait_for_idle(apps=[APP_NAME, DUMMY_NAME_2])
    await ops_test.model.add_relation(APP_NAME, DUMMY_NAME_2)
    await ops_test.model.wait_for_idle(apps=[APP_NAME, DUMMY_NAME_2])
    assert ops_test.model.applications[APP_NAME].status == "active"
    assert ops_test.model.applications[DUMMY_NAME_2].status == "active"

    assert ping_servers(ops_test)
    for unit in ops_test.model.applications[APP_NAME].units:
        jaas_config = check_jaas_config(model_full_name=ops_test.model_full_name, unit=unit.name)
        assert "sync" in jaas_config
        assert "super" in jaas_config

        # includes the related units
        assert len(jaas_config) == 4


@pytest.mark.abort_on_fail
async def test_scale_up_gets_new_jaas_users(ops_test: OpsTest):
    await ops_test.model.applications[APP_NAME].add_units(count=1)
    await ops_test.model.block_until(lambda: len(ops_test.model.applications[APP_NAME].units) == 4)

    await ops_test.model.wait_for_idle(
        apps=[APP_NAME], status="active", timeout=1000, idle_period=30
    )

    assert ping_servers(ops_test)
    for unit in ops_test.model.applications[APP_NAME].units:
        jaas_config = check_jaas_config(model_full_name=ops_test.model_full_name, unit=unit.name)
        assert "sync" in jaas_config
        assert "super" in jaas_config

        # includes the related units
        assert len(jaas_config) == 4


async def test_remove_applications(ops_test: OpsTest):
    await ops_test.model.applications[DUMMY_NAME_1].remove()
    await ops_test.model.applications[DUMMY_NAME_2].remove()

    await ops_test.model.wait_for_idle(
        apps=[APP_NAME], status="active", timeout=1000, idle_period=60
    )

    assert ping_servers(ops_test)
    for unit in ops_test.model.applications[APP_NAME].units:
        jaas_config = check_jaas_config(model_full_name=ops_test.model_full_name, unit=unit.name)
        assert "sync" in jaas_config
        assert "super" in jaas_config

        # doesn't include the departed units
        assert len(jaas_config) == 2
