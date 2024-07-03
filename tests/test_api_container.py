from privacyidea.lib.container import init_container, find_container_by_serial, add_tokens_to_container, assign_user
from privacyidea.lib.policy import set_policy, SCOPE, ACTION, delete_policy
from privacyidea.lib.realm import set_realm
from privacyidea.lib.resolver import save_resolver
from privacyidea.lib.token import init_token
from privacyidea.lib.user import User
from tests.base import MyApiTestCase


class APIContainerAuthorization(MyApiTestCase):
    def setUp(self):
        rid = save_resolver({"resolver": self.resolvername1,
                             "type": "passwdresolver",
                             "fileName": "tests/testdata/passwords"})
        self.assertGreater(rid, 0)

        (added, failed) = set_realm(self.realm1, [{'name': self.resolvername1}])
        self.assertEqual(0, len(failed))
        self.assertEqual(1, len(added))

        user = User(login="root",
                    realm=self.realm1,
                    resolver=self.resolvername1)

        user_str = "{0!s}".format(user)
        self.assertEqual("<root.resolver1@realm1>", user_str)

        self.assertFalse(user.is_empty())
        self.assertTrue(User().is_empty())

        user_repr = "{0!r}".format(user)
        expected = "User(login='root', realm='realm1', resolver='resolver1')"
        self.assertEqual(expected, user_repr)
        self.authenticate_selfservice_user()

    def request_denied_assert_403(self, url, data: dict, auth_token, method='POST'):
        with self.app.test_request_context(url,
                                           method=method,
                                           data=data,
                                           headers={'Authorization': auth_token}):
            res = self.app.full_dispatch_request()
            self.assertEqual(403, res.status_code, res.json)
            self.assertEqual(res.json["result"]["error"]["code"], 303)
            return res.json

    def request_assert_200(self, url, data: dict, auth_token, method='POST'):
        with self.app.test_request_context(url,
                                           method=method,
                                           data=data,
                                           headers={'Authorization': auth_token}):
            res = self.app.full_dispatch_request()
            self.assertEqual(200, res.status_code, res.json)
            self.assertTrue(res.json["result"]["status"])
            return res.json

    def create_container_for_user(self):
        set_policy("user_container_create", scope=SCOPE.USER, action=ACTION.CONTAINER_CREATE)
        with self.app.test_request_context('/container/init',
                                           method='POST',
                                           data={"type": "generic"},
                                           headers={'Authorization': self.at_user}):
            res = self.app.full_dispatch_request()
            self.assertEqual(res.status_code, 200)
        container_serial = res.json["result"]["value"]["container_serial"]
        self.assertGreater(len(container_serial), 0)
        delete_policy("user_container_create")
        return container_serial

    def test_01_user_create_allowed(self):
        self.create_container_for_user()

    def test_02_user_create_denied(self):
        # Set a random policy so that user action are defined
        set_policy("policy", scope=SCOPE.USER, action=ACTION.CONTAINER_DESCRIPTION)
        self.request_denied_assert_403('/container/init', {"type": "Smartphone", "description": "test description!!"},
                                       self.at_user)
        delete_policy("policy")

    def test_03_user_delete_allowed(self):
        set_policy("policy", scope=SCOPE.USER, action=ACTION.CONTAINER_DELETE)
        container_serial = self.create_container_for_user()
        self.request_assert_200(f"/container/{container_serial}", {}, self.at_user, method='DELETE')
        delete_policy("policy")

    def test_04_user_delete_denied(self):
        # user not has 'delete' rights
        set_policy("policy", scope=SCOPE.USER, action=ACTION.CONTAINER_CREATE)
        container_serial = self.create_container_for_user()
        self.request_denied_assert_403(f"/container/{container_serial}", {}, self.at_user, method='DELETE')
        delete_policy("policy")

        # user is not the owner of the container
        set_policy("policy", scope=SCOPE.USER, action=ACTION.CONTAINER_DELETE)
        container_serial = init_container({"type": "generic", "user": "hans", "realm": self.realm1})
        self.request_denied_assert_403(f"/container/{container_serial}", {}, self.at_user, method='DELETE')
        delete_policy("policy")

    def test_05_user_description_allowed(self):
        set_policy("policy", scope=SCOPE.USER, action=ACTION.CONTAINER_DESCRIPTION)
        container_serial = self.create_container_for_user()
        self.request_assert_200(f"/container/{container_serial}/description", {"description": "test"}, self.at_user,
                                method='POST')
        delete_policy("policy")

    def test_06_user_description_denied(self):
        # user not has 'description' rights
        set_policy("policy", scope=SCOPE.USER, action=ACTION.CONTAINER_DELETE)
        container_serial = self.create_container_for_user()
        self.request_denied_assert_403(f"/container/{container_serial}/description", {"description": "test"},
                                       self.at_user,
                                       method='POST')
        delete_policy("policy")

        # user is not the owner of the container
        set_policy("policy", scope=SCOPE.USER, action=ACTION.CONTAINER_DESCRIPTION)
        container_serial = init_container({"type": "generic", "user": "hans", "realm": self.realm1})
        self.request_denied_assert_403(f"/container/{container_serial}/description", {"description": "test"},
                                       self.at_user, method='POST')
        delete_policy("policy")

    def test_07_user_state_allowed(self):
        set_policy("policy", scope=SCOPE.USER, action=ACTION.CONTAINER_STATE)
        container_serial = self.create_container_for_user()
        self.request_assert_200(f"/container/{container_serial}/states", {"states": "active, damaged, lost"},
                                self.at_user,
                                method='POST')
        delete_policy("policy")

    def test_08_user_state_denied(self):
        # user not has 'state' rights
        set_policy("policy", scope=SCOPE.USER, action=ACTION.CONTAINER_DELETE)
        container_serial = self.create_container_for_user()
        self.request_denied_assert_403(f"/container/{container_serial}/states", {"states": "active, damaged, lost"},
                                       self.at_user,
                                       method='POST')
        delete_policy("policy")

        # user is not the owner of the container
        set_policy("policy", scope=SCOPE.USER, action=ACTION.CONTAINER_STATE)
        container_serial = init_container({"type": "generic", "user": "hans", "realm": self.realm1})
        self.request_denied_assert_403(f"/container/{container_serial}/states", {"states": "active, damaged, lost"},
                                       self.at_user, method='POST')
        delete_policy("policy")

    def test_09_user_add_token_allowed(self):
        set_policy("policy", scope=SCOPE.USER, action=ACTION.CONTAINER_ADD_TOKEN)
        container_serial = self.create_container_for_user()
        container = find_container_by_serial(container_serial)
        container_owner = container.get_users()[0]
        token = init_token({"genkey": "1"}, user=container_owner)
        token_serial = token.get_serial()
        json = self.request_assert_200(f"/container/{container_serial}/add", {"serial": token_serial}, self.at_user,
                                       method='POST')
        self.assertTrue(json["result"]["value"][token_serial])

        delete_policy("policy")

    def test_10_user_add_token_denied(self):
        # Arrange
        container_serial = self.create_container_for_user()
        my_token = init_token({"genkey": "1"}, user=User("selfservice", self.realm1, self.resolvername1))
        my_token_serial = my_token.get_serial()

        # User has not 'add' rights
        set_policy("policy", scope=SCOPE.USER, action=ACTION.CONTAINER_DELETE)
        self.request_denied_assert_403(f"/container/{container_serial}/add", {"serial": my_token_serial}, self.at_user,
                                       method='POST')
        delete_policy("policy")

        # User has 'add' rights but is not the owner of the token
        user = User(login="hans", realm=self.realm1, resolver=self.resolvername1)
        token = init_token({"genkey": "1"}, user=user)
        token_serial = token.get_serial()
        set_policy("policy", scope=SCOPE.USER, action=ACTION.CONTAINER_ADD_TOKEN)
        json = self.request_assert_200(f"/container/{container_serial}/add", {"serial": token_serial}, self.at_user,
                                       method='POST')
        self.assertFalse(json["result"]["value"][token_serial])

        # User has 'add' rights but the token is already in a container from another user
        another_container_serial = init_container({"type": "generic", "user": user.login, "realm": user.realm})
        add_tokens_to_container(another_container_serial, [my_token_serial], User(), 'admin')
        self.request_denied_assert_403(f"/container/{container_serial}/add", {"serial": my_token_serial},
                                       self.at_user,
                                       method='POST')
        delete_policy("policy")

    def test_11_user_remove_token_allowed(self):
        set_policy("policy", scope=SCOPE.USER, action=ACTION.CONTAINER_REMOVE_TOKEN)
        container_serial = self.create_container_for_user()
        container = find_container_by_serial(container_serial)
        token = init_token({"genkey": "1"}, user=container.get_users()[0])
        token_serial = token.get_serial()
        container.add_token(token)

        json = self.request_assert_200(f"/container/{container_serial}/remove", {"serial": token_serial}, self.at_user,
                                       method='POST')
        self.assertTrue(json["result"]["value"][token_serial])
        delete_policy("policy")

    def test_12_user_remove_token_denied(self):
        # User has not 'remove' rights
        container_serial = self.create_container_for_user()
        my_token = init_token({"genkey": "1"}, user=User("selfservice", self.realm1, self.resolvername1))
        my_token_serial = my_token.get_serial()
        container = find_container_by_serial(container_serial)
        container.add_token(my_token)
        set_policy("policy", scope=SCOPE.USER, action=ACTION.CONTAINER_DELETE)
        self.request_denied_assert_403(f"/container/{container_serial}/remove", {"serial": my_token_serial},
                                       self.at_user, method='POST')
        delete_policy("policy")

        # User has 'remove' rights but is not the owner of the token
        set_policy("policy", scope=SCOPE.USER, action=ACTION.CONTAINER_REMOVE_TOKEN)
        user = User(login="hans", realm=self.realm1, resolver=self.resolvername1)
        token = init_token({"genkey": "1"}, user=user)
        token_serial = token.get_serial()
        container.add_token(token)
        json = self.request_assert_200(f"/container/{container_serial}/remove", {"serial": token_serial}, self.at_user,
                                       method='POST')
        self.assertFalse(json["result"]["value"][token_serial])

        # User has 'remove' rights but is not the owner of the container
        another_container_serial = init_container({"type": "generic", "user": "hans", "realm": self.realm1})
        another_container = find_container_by_serial(another_container_serial)
        another_container.add_token(my_token)
        self.request_denied_assert_403(f"/container/{another_container_serial}/remove", {"serial": my_token_serial},
                                       self.at_user, method='POST')

        delete_policy("policy")

    def test_13_user_assign_user_allowed(self):
        set_policy("policy", scope=SCOPE.USER, action=ACTION.CONTAINER_ASSIGN_USER)
        container_serial = init_container({"type": "generic"})
        self.request_assert_200(f"/container/{container_serial}/assign", {"realm": "realm1", "user": "root"},
                                self.at_user)
        delete_policy("policy")

    def test_14_user_assign_user_denied(self):
        set_policy("policy", scope=SCOPE.USER, action=ACTION.CONTAINER_DELETE)
        container_serial = self.create_container_for_user()
        self.request_denied_assert_403(f"/container/{container_serial}/assign",
                                       {"realm": "realm1", "user": "selfservice"},
                                       self.at_user)
        delete_policy("policy")

    def test_15_user_remove_user_allowed(self):
        # user is allowed to unassign from its own container
        set_policy("policy", scope=SCOPE.USER, action=ACTION.CONTAINER_UNASSIGN_USER)
        container_serial = self.create_container_for_user()
        self.request_assert_200(f"/container/{container_serial}/unassign", {"realm": "realm1", "user": "root"},
                                self.at_user)
        delete_policy("policy")

    def test_16_user_remove_user_denied(self):
        # User has no 'unassign' rights
        set_policy("policy", scope=SCOPE.USER, action=ACTION.CONTAINER_DELETE)
        container_serial = self.create_container_for_user()
        self.request_denied_assert_403(f"/container/{container_serial}/unassign",
                                       {"realm": "realm1", "user": "selfservice"}, self.at_user)
        delete_policy("policy")

        # User is not allowed to unassign users from a container that is not his own
        set_policy("policy", scope=SCOPE.USER, action=ACTION.CONTAINER_UNASSIGN_USER)
        container_serial = init_container({"type": "generic"})
        user = User(login="hans", realm=self.realm1, resolver=self.resolvername1)
        container = find_container_by_serial(container_serial)
        container.add_user(user)
        self.request_denied_assert_403(f"/container/{container_serial}/unassign", {"realm": "realm1", "user": "root"},
                                       self.at_user)
        delete_policy("policy")

    def test_17_admin_create_allowed(self):
        set_policy("policy", scope=SCOPE.ADMIN, action=ACTION.CONTAINER_CREATE)
        json = self.request_assert_200('/container/init', {"type": "generic"}, self.at)
        self.assertGreater(len(json["result"]["value"]["container_serial"]), 0)
        delete_policy("policy")

    def test_18_admin_create_denied(self):
        set_policy("policy", scope=SCOPE.ADMIN, action=ACTION.CONTAINER_DESCRIPTION)
        self.request_denied_assert_403('/container/init', {"type": "Smartphone", "description": "test description!!"},
                                       self.at)
        delete_policy("policy")

    def test_19_admin_delete_allowed(self):
        set_policy("policy", scope=SCOPE.ADMIN, action=ACTION.CONTAINER_DELETE)
        container_serial = self.create_container_for_user()
        self.request_assert_200(f"/container/{container_serial}", {}, self.at, method='DELETE')
        delete_policy("policy")

    def test_20_admin_delete_denied(self):
        set_policy("policy", scope=SCOPE.ADMIN, action=ACTION.CONTAINER_CREATE)
        container_serial = self.create_container_for_user()
        self.request_denied_assert_403(f"/container/{container_serial}", {}, self.at, method='DELETE')
        delete_policy("policy")

    def test_21_admin_description_allowed(self):
        set_policy("policy", scope=SCOPE.ADMIN, action=ACTION.CONTAINER_DESCRIPTION)
        container_serial = self.create_container_for_user()
        self.request_assert_200(f"/container/{container_serial}/description", {"description": "test"}, self.at,
                                method='POST')
        delete_policy("policy")

    def test_22_admin_description_denied(self):
        set_policy("policy", scope=SCOPE.ADMIN, action=ACTION.CONTAINER_DELETE)
        container_serial = self.create_container_for_user()
        self.request_denied_assert_403(f"/container/{container_serial}/description", {"description": "test"},
                                       self.at, method='POST')
        delete_policy("policy")

    def test_23_admin_state_allowed(self):
        set_policy("policy", scope=SCOPE.ADMIN, action=ACTION.CONTAINER_STATE)
        container_serial = self.create_container_for_user()
        self.request_assert_200(f"/container/{container_serial}/states", {"states": "active, damaged, lost"},
                                self.at, method='POST')
        delete_policy("policy")

    def test_24_admin_state_denied(self):
        set_policy("policy", scope=SCOPE.ADMIN, action=ACTION.CONTAINER_DELETE)
        container_serial = self.create_container_for_user()
        self.request_denied_assert_403(f"/container/{container_serial}/states", {"states": "active, damaged, lost"},
                                       self.at, method='POST')
        delete_policy("policy")

    def test_25_admin_add_token_allowed(self):
        set_policy("policy", scope=SCOPE.ADMIN, action=ACTION.CONTAINER_ADD_TOKEN)
        container_serial = self.create_container_for_user()
        token = init_token({"genkey": "1"})
        token_serial = token.get_serial()
        json = self.request_assert_200(f"/container/{container_serial}/add", {"serial": token_serial}, self.at,
                                       method='POST')
        self.assertTrue(json["result"]["value"][token_serial])
        delete_policy("policy")

    def test_26_admin_add_token_denied(self):
        set_policy("policy", scope=SCOPE.ADMIN, action=ACTION.CONTAINER_DELETE)
        container_serial = self.create_container_for_user()
        token = init_token({"genkey": "1"})
        token_serial = token.get_serial()
        self.request_denied_assert_403(f"/container/{container_serial}/add", {"serial": token_serial}, self.at,
                                       method='POST')
        delete_policy("policy")

    def test_27_admin_remove_token_allowed(self):
        set_policy("policy", scope=SCOPE.ADMIN, action=ACTION.CONTAINER_REMOVE_TOKEN)
        container_serial = self.create_container_for_user()
        token = init_token({"genkey": "1"})
        token_serial = token.get_serial()
        container = find_container_by_serial(container_serial)
        container.add_token(token)
        json = self.request_assert_200(f"/container/{container_serial}/remove", {"serial": token_serial}, self.at,
                                       method='POST')
        self.assertTrue(json["result"]["value"][token_serial])
        delete_policy("policy")

    def test_28_admin_remove_token_denied(self):
        set_policy("policy", scope=SCOPE.ADMIN, action=ACTION.CONTAINER_DELETE)
        container_serial = self.create_container_for_user()
        token = init_token({"genkey": "1"})
        token_serial = token.get_serial()
        container = find_container_by_serial(container_serial)
        container.add_token(token)
        self.request_denied_assert_403(f"/container/{container_serial}/remove", {"serial": token_serial}, self.at,
                                       method='POST')
        delete_policy("policy")

    def test_29_admin_assign_user_allowed(self):
        set_policy("policy", scope=SCOPE.ADMIN, action=ACTION.CONTAINER_ASSIGN_USER)
        container_serial = init_container({"type": "generic"})
        self.request_assert_200(f"/container/{container_serial}/assign",
                                {"realm": "realm1", "user": "root", "resolver": self.resolvername1}, self.at)
        delete_policy("policy")

    def test_30_admin_assign_user_denied(self):
        set_policy("policy", scope=SCOPE.ADMIN, action=ACTION.CONTAINER_DELETE)
        container_serial = self.create_container_for_user()
        self.request_denied_assert_403(f"/container/{container_serial}/assign",
                                       {"realm": "realm1", "user": "root", "resolver": self.resolvername1}, self.at)
        delete_policy("policy")

    def test_31_admin_remove_user_allowed(self):
        set_policy("policy", scope=SCOPE.ADMIN, action=ACTION.CONTAINER_UNASSIGN_USER)
        container_serial = init_container({"type": "generic", "user": "root", "realm": self.realm1})
        self.request_assert_200(f"/container/{container_serial}/unassign",
                                {"realm": "realm1", "user": "root", "resolver": self.resolvername1}, self.at)
        delete_policy("policy")

    def test_32_admin_remove_user_denied(self):
        set_policy("policy", scope=SCOPE.ADMIN, action=ACTION.CONTAINER_DELETE)
        container_serial = init_container({"type": "generic", "user": "root", "realm": self.realm1})
        self.request_denied_assert_403(f"/container/{container_serial}/unassign",
                                       {"realm": "realm1", "user": "root", "resolver": self.resolvername1}, self.at)
        delete_policy("policy")

    def test_33_user_container_realms_denied(self):
        # Editing the container realms is an admin action and therefore only ever allowed for admins
        # But this returns a 401 from the @admin_required decorator
        container_serial = self.create_container_for_user()
        set_policy("policy", scope=SCOPE.USER, action=ACTION.CONTAINER_DELETE)

        with self.app.test_request_context(f"/container/{container_serial}/realms", method='POST',
                                           data={"realms": "realm1"}, headers={'Authorization': self.at_user}):
            res = self.app.full_dispatch_request()
            self.assertEqual(401, res.status_code, res.json)
        delete_policy("policy")

    def test_34_admin_container_realms_allowed(self):
        set_policy("policy", scope=SCOPE.ADMIN, action=ACTION.CONTAINER_REALMS)
        container_serial = self.create_container_for_user()
        self.request_assert_200(f"/container/{container_serial}/realms", {"realms": "realm1"}, self.at)
        delete_policy("policy")

    def test_35_admin_container_realms_denied(self):
        set_policy("policy", scope=SCOPE.ADMIN, action=ACTION.CONTAINER_DELETE)
        container_serial = self.create_container_for_user()
        self.request_denied_assert_403(f"/container/{container_serial}/realms", {"realms": "realm1"}, self.at)
        delete_policy("policy")


class APIContainer(MyApiTestCase):

    def request_assert_success(self, url, data: dict, auth_token, method='POST'):
        with self.app.test_request_context(url,
                                           method=method,
                                           data=data,
                                           headers={'Authorization': auth_token}):
            res = self.app.full_dispatch_request()
            self.assertEqual(200, res.status_code, res.json)
            self.assertTrue(res.json["result"]["status"])
            return res.json

    def request_assert_error(self, status_code, url, data: dict, auth_token, method='POST'):
        with self.app.test_request_context(url,
                                           method=method,
                                           data=data,
                                           headers={'Authorization': auth_token}):
            res = self.app.full_dispatch_request()
            self.assertEqual(status_code, res.status_code, res.json)
            self.assertFalse(res.json["result"]["status"])
            return res.json

    def request_assert_405(self, url, data: dict, auth_token, method='POST'):
        with self.app.test_request_context(url,
                                           method=method,
                                           data=data,
                                           headers={'Authorization': auth_token}):
            res = self.app.full_dispatch_request()
            self.assertEqual(405, res.status_code, res.json)
            return res.json

    def request_assert_404_no_result(self, url, data: dict, auth_token, method='POST'):
        with self.app.test_request_context(url,
                                           method=method,
                                           data=data,
                                           headers={'Authorization': auth_token}):
            res = self.app.full_dispatch_request()
            self.assertEqual(404, res.status_code, res.json)

    def test_00_init_delete_container_success(self):
        # Init container
        payload = {"type": "Smartphone", "description": "test description!!"}
        res = self.request_assert_success('/container/init', payload, self.at, 'POST')
        cserial = res["result"]["value"]["container_serial"]
        self.assertTrue(len(cserial) > 1)

        # Delete the container
        json = self.request_assert_success(f"container/{cserial}", {}, self.at, 'DELETE')
        self.assertTrue(json["result"]["value"])

    def test_01_init_container_fail(self):
        # Init with non-existing type
        payload = {"type": "wrongType", "description": "test description!!"}
        json = self.request_assert_error(400, '/container/init', payload, self.at, 'POST')
        error = json["result"]["error"]
        error_code = error["code"]
        error_msg = error["message"]
        self.assertEqual(404, error_code)
        self.assertEqual("ERR404: Type 'wrongType' is not a valid type!", error_msg)

        # Init without type
        json = self.request_assert_error(400, '/container/init', {}, self.at, 'POST')
        error = json["result"]["error"]
        error_code = error["code"]
        error_msg = error["message"]
        self.assertEqual(404, error_code)
        self.assertEqual("ERR404: Type parameter is required!", error_msg)

    def test_02_delete_container_fail(self):
        # Delete non-existing container
        json = self.request_assert_error(404, '/container/wrong_serial', {}, self.at, 'DELETE')
        error = json["result"]["error"]
        error_code = error["code"]
        error_msg = error["message"]
        self.assertEqual(601, error_code)
        self.assertEqual("Unable to find container with serial wrong_serial.", error_msg)

        # Call without serial
        self.request_assert_405('/container/', {}, self.at, 'DELETE')

    def test_03_assign_user_fail(self):
        # Arrange
        container_serial = init_container({"type": "generic"})

        # Assign without realm
        payload = {"user": "hans"}
        json = self.request_assert_error(400, f'/container/{container_serial}/assign',
                                         payload, self.at, 'POST')
        error = json["result"]["error"]
        self.assertEqual(904, error["code"])
        self.assertEqual("ERR904: The user can not be found in any resolver in this realm!", error["message"])

        # Assign user with non-existing realm
        payload = {"user": "hans", "realm": "non_existing"}
        json = self.request_assert_error(400, f'/container/{container_serial}/assign',
                                         payload, self.at, 'POST')
        error = json["result"]["error"]
        self.assertEqual(904, error["code"])
        self.assertEqual("ERR904: The user can not be found in any resolver in this realm!", error["message"])

        # Assign without user
        self.setUp_user_realm2()
        payload = {"realm": self.realm2}
        json = self.request_assert_error(400, f'/container/{container_serial}/assign',
                                         payload, self.at, 'POST')
        error = json["result"]["error"]
        self.assertEqual(905, error["code"])
        self.assertEqual("ERR905: Missing parameter: 'user'", error["message"])

    def test_04_assign_multiple_users_fails(self):
        # Arrange
        container_serial = init_container({"type": "generic"})
        self.setUp_user_realms()
        payload = {"user": "hans", "realm": self.realm1}

        # Assign with user and realm
        json = self.request_assert_success(f'/container/{container_serial}/assign', payload, self.at, 'POST')
        self.assertTrue(json["result"]["value"])

        # Assign another user fails
        payload = {"user": "cornelius", "realm": self.realm1}
        json = self.request_assert_error(400, f'/container/{container_serial}/assign',
                                           payload, self.at, 'POST')
        error = json["result"]["error"]
        self.assertEqual(301, error["code"])
        self.assertEqual("ERR301: This container is already assigned to another user.", error["message"])

    def test_05_assign_unassign_user_success(self):
        # Arrange
        container_serial = init_container({"type": "generic"})
        self.setUp_user_realms()
        payload = {"user": "hans", "realm": self.realm1}

        # Assign with user and realm
        json = self.request_assert_success(f'/container/{container_serial}/assign', payload, self.at, 'POST')
        self.assertTrue(json["result"]["value"])

        # Unassign
        json = self.request_assert_success(f'/container/{container_serial}/unassign',
                                           payload, self.at, 'POST')
        self.assertTrue(json["result"]["value"])

    def test_06_assign_without_realm(self):
        # If no realm is passed the default realm is set in before_request
        # Arrange
        container_serial = init_container({"type": "generic"})
        self.setUp_user_realm2()
        self.setUp_user_realm3()
        payload = {"user": "hans"}

        # Assign
        json = self.request_assert_success(f'/container/{container_serial}/assign',
                                           payload, self.at, 'POST')
        self.assertTrue(json["result"]["value"])
        # Used default realm is correct
        container = find_container_by_serial(container_serial)
        owner = container.get_users()[0]
        self.assertTrue(owner.login == "hans")
        self.assertTrue(owner.realm == self.realm2)

        # Assign without realm where default realm is not correct
        container_serial = init_container({"type": "generic"})
        payload = {"user": "root"}
        json = self.request_assert_error(400, f'/container/{container_serial}/assign',
                                         payload, self.at, 'POST')
        error = json["result"]["error"]
        self.assertEqual(904, error["code"])
        self.assertEqual("ERR904: The user can not be found in any resolver in this realm!", error["message"])

    def test_07_unassign_fail(self):
        # Arrange
        container_serial = init_container({"type": "generic"})

        # Unassign without realm
        payload = {"user": "root"}
        json = self.request_assert_error(400, f'/container/{container_serial}/unassign',
                                         payload, self.at, 'POST')
        error = json["result"]["error"]
        self.assertEqual(904, error["code"])
        self.assertEqual("ERR904: The user can not be found in any resolver in this realm!", error["message"])

        # Unassign user with non-existing realm
        payload = {"user": "hans", "realm": "non_existing"}
        json = self.request_assert_error(400, f'/container/{container_serial}/unassign',
                                         payload, self.at, 'POST')
        error = json["result"]["error"]
        self.assertEqual(904, error["code"])
        self.assertEqual("ERR904: The user can not be found in any resolver in this realm!", error["message"])

        # Unassign without user
        self.setUp_user_realm2()
        payload = {"realm": self.realm2}
        json = self.request_assert_error(400, f'/container/{container_serial}/unassign',
                                         payload, self.at, 'POST')
        error = json["result"]["error"]
        self.assertEqual(905, error["code"])
        self.assertEqual("ERR905: Missing parameter: 'user'", error["message"])

        # Unassign not assigned user
        payload = {"user": "cornelius", "realm": self.realm2}
        json = self.request_assert_success(f'/container/{container_serial}/unassign',
                                           payload, self.at, 'POST')
        self.assertFalse(json["result"]["value"])

    def test_08_set_realms_success(self):
        # Arrange
        self.setUp_user_realms()
        self.setUp_user_realm2()
        container_serial = init_container({"type": "generic"})

        # Set existing realms
        payload = {"realms": self.realm1 + "," + self.realm2}
        json = self.request_assert_success(f'/container/{container_serial}/realms', payload, self.at, 'POST')
        result = json["result"]
        self.assertTrue(result["value"])
        self.assertTrue(result["value"]["deleted"])
        self.assertTrue(result["value"][self.realm1])
        self.assertTrue(result["value"][self.realm2])

        # Set no realm shall remove all realms for the container
        payload = {"realms": ""}
        json = self.request_assert_success(f'/container/{container_serial}/realms', payload, self.at, 'POST')
        result = json["result"]
        self.assertTrue(result["value"])
        self.assertTrue(result["value"]["deleted"])
        self.assertNotIn(self.realm1, result["value"].keys())
        self.assertNotIn(self.realm2, result["value"].keys())

        # Automatically add the user realms
        container_serial = init_container({"type": "generic", "user": "hans", "realm": self.realm1})
        payload = {"realms": self.realm2}
        json = self.request_assert_success(f'/container/{container_serial}/realms', payload, self.at, 'POST')
        self.assertTrue(json["result"]["value"][self.realm1])
        self.assertTrue(json["result"]["value"][self.realm2])

    def test_09_set_realms_fail(self):
        # Arrange
        self.setUp_user_realms()
        self.setUp_user_realm2()
        container_serial = init_container({"type": "generic"})

        # Missing realm parameter
        json = self.request_assert_error(400, f'/container/{container_serial}/realms',
                                         {}, self.at, 'POST')
        error = json["result"]["error"]
        self.assertEqual(905, error["code"])
        self.assertEqual("ERR905: Missing parameter: 'realms'", error["message"])

        # Set non-existing realm
        payload = {"realms": "nonexistingrealm"}
        json = self.request_assert_success(f'/container/{container_serial}/realms', payload, self.at, 'POST')
        result = json.get("result")
        self.assertFalse(result["value"]["nonexistingrealm"])

        # Missing container serial
        self.request_assert_405('/container/realms', {"realms": [self.realm1]}, self.at, 'POST')

    def test_10_set_description_success(self):
        # Arrange
        container_serial = init_container({"type": "generic", "description": "test container"})

        # Set description
        payload = {"description": "new description"}
        json = self.request_assert_success(f'/container/{container_serial}/description',
                                           payload, self.at, 'POST')
        self.assertTrue(json["result"]["value"])

        # Set description
        payload = {"description": ""}
        json = self.request_assert_success(f'/container/{container_serial}/description',
                                           payload, self.at, 'POST')
        self.assertTrue(json["result"]["value"])

    def test_11_set_description_fail(self):
        # Arrange
        container_serial = init_container({"type": "generic", "description": "test container"})

        # Missing description parameter
        json = self.request_assert_error(400, f'/container/{container_serial}/description',
                                         {}, self.at, 'POST')
        error = json["result"]["error"]
        self.assertEqual(905, error["code"])
        self.assertEqual("ERR905: Missing parameter: 'description'", error["message"])

        # Description parameter is None
        json = self.request_assert_error(400, f'/container/{container_serial}/description',
                                         {"description": None}, self.at, 'POST')
        error = json["result"]["error"]
        self.assertEqual(905, error["code"])
        self.assertEqual("ERR905: Missing parameter: 'description'", error["message"])

        # Missing container serial
        self.request_assert_405('/container/description', {"description": "new description"},
                                self.at, 'POST')

    def test_12_set_states_success(self):
        # Arrange
        container_serial = init_container({"type": "generic", "description": "test container"})

        # Set states
        payload = {"states": "active,damaged,lost"}
        json = self.request_assert_success(f'/container/{container_serial}/states',
                                           payload, self.at, 'POST')
        self.assertTrue(json["result"]["value"])
        self.assertTrue(json["result"]["value"]["active"])
        self.assertTrue(json["result"]["value"]["damaged"])
        self.assertTrue(json["result"]["value"]["lost"])

    def test_13_set_states_fail(self):
        # Arrange
        container_serial = init_container({"type": "generic", "description": "test container"})

        # Missing states parameter
        json = self.request_assert_error(400, f'/container/{container_serial}/states',
                                         {}, self.at, 'POST')
        error = json["result"]["error"]
        self.assertEqual(905, error["code"])
        self.assertEqual("ERR905: Missing parameter: 'states'", error["message"])

        # Missing container serial
        self.request_assert_405('/container/states', {"states": "active,damaged,lost"},
                                self.at, 'POST')

    def test_14_set_container_info_success(self):
        # Arrange
        container_serial = init_container({"type": "generic", "description": "test container"})

        # Set info
        self.request_assert_success(f'/container/{container_serial}/info/key1',
                                    {"value": "value1"}, self.at, 'POST')

    def test_15_set_container_info_fail(self):
        # Arrange
        container_serial = init_container({"type": "generic"})

        # Missing value parameter
        json = self.request_assert_error(400, f'/container/{container_serial}/info/key1',
                                         {}, self.at, 'POST')
        error = json["result"]["error"]
        self.assertEqual(905, error["code"])
        self.assertEqual("ERR905: Missing parameter: 'value'", error["message"])

        # Missing container serial
        self.request_assert_404_no_result('/container/info/key1', {"value": "value1"}, self.at, 'POST')

        # Missing key
        self.request_assert_404_no_result(f'/container/{container_serial}/info/',
                                          {"value": "value1"}, self.at, 'POST')

    def test_16_update_last_seen(self):
        # Arrange
        container_serial = init_container({"type": "generic", "description": "test container"})

        # Update last seen success
        self.request_assert_success(f'/container/{container_serial}/lastseen',
                                    {}, self.at, 'POST')

        # Update last seen invalid container serial
        self.request_assert_error(404, f'/container/wrong_serial/lastseen',
                                  {}, self.at, 'POST')

        # Update last seen without container serial
        self.request_assert_405('/container/lastseen', {}, self.at, 'POST')

    def test_17_add_remove_token_success(self):
        # Arrange
        container_serial = init_container({"type": "generic"})
        hotp_01 = init_token({"genkey": "1"})
        hotp_01_serial = hotp_01.get_serial()
        hotp_02 = init_token({"genkey": "1"})
        hotp_02_serial = hotp_02.get_serial()
        hotp_03 = init_token({"genkey": "1"})
        hotp_03_serial = hotp_03.get_serial()

        # Add single token
        json = self.request_assert_success(f'/container/{container_serial}/add',
                                           {"serial": hotp_01_serial}, self.at, 'POST')
        self.assertTrue(json["result"]["value"][hotp_01_serial])

        # Remove single token
        json = self.request_assert_success(f'/container/{container_serial}/remove',
                                           {"serial": hotp_01_serial}, self.at, 'POST')
        self.assertTrue(json["result"]["value"][hotp_01_serial])

        # Add multiple tokens
        json = self.request_assert_success(f'/container/{container_serial}/add',
                                           {"serial": f"{hotp_01_serial},{hotp_02_serial},{hotp_03_serial}"},
                                           self.at, 'POST')
        self.assertTrue(json["result"]["value"][hotp_01_serial])
        self.assertTrue(json["result"]["value"][hotp_02_serial])
        self.assertTrue(json["result"]["value"][hotp_03_serial])

        # Remove multiple tokens with spaces in list
        json = self.request_assert_success(f'/container/{container_serial}/remove',
                                           {"serial": f"{hotp_01_serial}, {hotp_02_serial}, {hotp_03_serial}"},
                                           self.at, 'POST')
        self.assertTrue(json["result"]["value"][hotp_01_serial])
        self.assertTrue(json["result"]["value"][hotp_02_serial])
        self.assertTrue(json["result"]["value"][hotp_03_serial])

        # Add multiple tokens with spaces in list
        json = self.request_assert_success(f'/container/{container_serial}/add',
                                           {"serial": f"{hotp_01_serial}, {hotp_02_serial}, {hotp_03_serial}"},
                                           self.at, 'POST')
        self.assertTrue(json["result"]["value"][hotp_01_serial])
        self.assertTrue(json["result"]["value"][hotp_02_serial])
        self.assertTrue(json["result"]["value"][hotp_03_serial])

        # Remove multiple tokens
        json = self.request_assert_success(f'/container/{container_serial}/remove',
                                           {"serial": f"{hotp_01_serial},{hotp_02_serial},{hotp_03_serial}"},
                                           self.at, 'POST')
        self.assertTrue(json["result"]["value"][hotp_01_serial])
        self.assertTrue(json["result"]["value"][hotp_02_serial])
        self.assertTrue(json["result"]["value"][hotp_03_serial])

    def test_18_add_token_fail(self):
        # Arrange
        container_serial = init_container({"type": "generic"})
        hotp_01 = init_token({"genkey": "1"})
        hotp_01_serial = hotp_01.get_serial()

        # Add token without serial
        json = self.request_assert_error(400, f'/container/{container_serial}/add',
                                         {}, self.at, 'POST')
        error = json["result"]["error"]
        self.assertEqual(905, error["code"])
        self.assertEqual("ERR905: Missing parameter: 'serial'", error["message"])

        # Add token without container serial
        self.request_assert_405('/container/add', {"serial": hotp_01_serial}, self.at, 'POST')

    def test_19_remove_token_fail(self):
        # Arrange
        container_serial = init_container({"type": "generic"})
        hotp_01 = init_token({"genkey": "1"})
        hotp_01_serial = hotp_01.get_serial()
        add_tokens_to_container(container_serial, [hotp_01_serial], user=User(), user_role="admin")

        # Remove token without serial
        json = self.request_assert_error(400, f'/container/{container_serial}/remove',
                                         {}, self.at, 'POST')
        error = json["result"]["error"]
        self.assertEqual(905, error["code"])
        self.assertEqual("ERR905: Missing parameter: 'serial'", error["message"])

        # Remove token without container serial
        self.request_assert_405('/container/remove', {"serial": hotp_01_serial}, self.at, 'POST')

    def test_20_get_state_types(self):
        json = self.request_assert_success('/container/statetypes', {}, self.at, 'GET')
        self.assertTrue(json["result"]["value"])
        self.assertIn("active", json["result"]["value"].keys())
        self.assertIn("disabled", json["result"]["value"]["active"])
        self.assertIn("lost", json["result"]["value"].keys())

    def test_21_get_types(self):
        json = self.request_assert_success('/container/types', {}, self.at, 'GET')
        self.assertTrue(json["result"]["value"])
        # check that all container types are included
        self.assertIn("smartphone", json["result"]["value"])
        self.assertIn("generic", json["result"]["value"])
        self.assertIn("yubikey", json["result"]["value"])
        # check that all properties are set
        self.assertIn("description", json["result"]["value"]["generic"])
        self.assertIn("token_types", json["result"]["value"]["generic"])

    def test_22_create_template(self):
        # Create template success
        json = self.request_assert_success(f'/container/generic/template/new_template',
                                           {}, self.at, 'POST')
        self.assertEqual(json["result"]["value"], 1)

        # Create template invalid container type
        self.request_assert_error(400, f'/container/wrong_type/template/new_template',
                                  {}, self.at, 'POST')

        # Create template without container serial
        self.request_assert_404_no_result('/container/template/new_template', {}, self.at, 'POST')

        # Create template without template name
        self.request_assert_404_no_result('/container/generic/template/', {}, self.at, 'POST')

    def test_23_get_template_options(self):
        # Success
        json = self.request_assert_success(f'/container/generic/template/options',
                                           {}, self.at, 'GET')
        self.assertTrue(json["result"]["value"])
        self.assertIn("token_count", json["result"]["value"].keys())

        # wrong type
        json = self.request_assert_error(400, f'/container/wrong_type/template/options',
                                         {}, self.at, 'GET')
        error = json["result"]["error"]
        self.assertEqual(905, error["code"])
        self.assertEqual("ERR905: Invalid container type", error["message"])

    def test_24_get_all_containers_paginate(self):
        # Arrange
        # Create containers
        types = ["Smartphone", "generic", "Yubikey", "Smartphone", "generic", "Yubikey"]
        container_serials = []
        for t in types:
            serial = init_container({"type": t, "description": "test container"})
            container_serials.append(serial)
        # Add token to container 1
        container = find_container_by_serial(container_serials[1])
        token = init_token({"genkey": "1"})
        token_serial = token.get_serial()
        add_tokens_to_container(container_serials[1], [token_serial], user=User(), user_role="admin")
        # Assign user to container 1
        self.setUp_user_realms()
        user_hans = User(login="hans", realm=self.realm1)
        container.add_user(user_hans)
        # Add second realm
        self.setUp_user_realm2()
        container.set_realms([self.realm2], add=True)
        # Add info
        container.add_container_info("key1", "value1")

        # filter for type
        json = self.request_assert_success('/container/',
                                           {"type": "generic", "pagesize": 15},
                                           self.at, 'GET')
        for container in json["result"]["value"]["containers"]:
            self.assertEqual(container["type"], "generic")

        # Filter for token serial
        json = self.request_assert_success('/container/',
                                           {"token_serial": token_serial, "pagesize": 15},
                                           self.at, 'GET')
        self.assertTrue(container_serials[1], json["result"]["value"]["containers"][0]["serial"])
        self.assertEqual(json["result"]["value"]["count"], 1)

        # Test output
        json = self.request_assert_success('/container/',
                                           {"container_serial": container_serials[1], "pagesize": 15, "page": 1},
                                           self.at, 'GET')
        containerdata = json["result"]["value"]
        # pagination
        self.assertEqual(1, containerdata["count"])
        self.assertIn("prev", containerdata.keys())
        self.assertIn("next", containerdata.keys())
        self.assertIn("current", containerdata.keys())
        self.assertEqual(1, len(containerdata["containers"]))
        # container data
        res_container = containerdata["containers"][0]
        self.assertEqual("generic", res_container["type"])
        self.assertEqual(container_serials[1], res_container["serial"])
        self.assertEqual("test container", res_container["description"])
        self.assertIn("last_seen", res_container.keys())
        self.assertIn("last_updated", res_container.keys())
        self.assertIn("active", res_container["states"])
        # tokens
        self.assertEqual(1, len(res_container["tokens"]))
        # user
        self.assertEqual(1, len(res_container["users"]))
        self.assertEqual(user_hans.login, res_container["users"][0]["user_name"])
        self.assertEqual(user_hans.realm, res_container["users"][0]["user_realm"])
        self.assertEqual(user_hans.resolver, res_container["users"][0]["user_resolver"])
        self.assertEqual(user_hans.uid, res_container["users"][0]["user_id"])
        # Realms
        self.assertIn(self.realm1, res_container["realms"])
        self.assertIn(self.realm2, res_container["realms"])
        # Info
        self.assertIn("key1", res_container["info"].keys())
        self.assertEqual("value1", res_container["info"]["key1"])

    def test_25_get_all_containers_paginate_invalid_params(self):
        init_container({"type": "generic", "description": "test container"})

        # filter for non-existing type
        json = self.request_assert_success('/container/',
                                           {"type": "non-existing", "pagesize": 15},
                                           self.at, 'GET')
        self.assertEqual(0, json["result"]["value"]["count"])

        # Filter for non existing token serial
        json = self.request_assert_success('/container/',
                                           {"token_serial": "non-existing", "pagesize": 15},
                                           self.at, 'GET')
        self.assertGreater(json["result"]["value"]["count"], 0)
