"""
Unit tests for plugin permission system.

Tests cover:
- Permission: Flag enum for permission definitions
- PermissionProfile: Pre-configured permission sets
- PluginPermissions: Permission management and checking
- PermissionValidator: Runtime permission enforcement
- FileAccessPolicy: Path-based access control
"""

import pytest
from pathlib import Path
from unittest.mock import Mock

from bot.rosey.core.plugin_permissions import (
    Permission,
    PermissionProfile,
    PROFILE_PERMISSIONS,
    PluginPermissions,
    PermissionError,
    PermissionValidator,
    FileAccessPolicy,
    create_restricted_permissions,
    get_file_policy,
    permission_summary
)


# ============================================================================
# Permission Tests
# ============================================================================

class TestPermission:
    """Test permission flag enum"""
    
    def test_permission_values(self):
        """Test basic permission values exist"""
        assert Permission.EXECUTE
        assert Permission.CONFIG_READ
        assert Permission.FILE_READ
        assert Permission.NETWORK_HTTP
        assert Permission.DATABASE_READ
        assert Permission.EVENT_PUBLISH
        assert Permission.PLATFORM_SEND
        assert Permission.SYSTEM_ENV
    
    def test_permission_combination(self):
        """Test combining permissions with bitwise operators"""
        basic = Permission.EXECUTE | Permission.CONFIG_READ
        
        assert Permission.EXECUTE in basic
        assert Permission.CONFIG_READ in basic
        assert Permission.FILE_WRITE not in basic
    
    def test_permission_flag_operations(self):
        """Test flag operations"""
        perms = Permission.EXECUTE | Permission.FILE_READ | Permission.FILE_WRITE
        
        # Check membership
        assert Permission.EXECUTE in perms
        assert Permission.FILE_READ in perms
        assert Permission.NETWORK_HTTP not in perms
        
        # Add permission
        perms |= Permission.NETWORK_HTTP
        assert Permission.NETWORK_HTTP in perms
        
        # Remove permission
        perms &= ~Permission.FILE_WRITE
        assert Permission.FILE_WRITE not in perms


# ============================================================================
# PermissionProfile Tests
# ============================================================================

class TestPermissionProfile:
    """Test permission profiles"""
    
    def test_profile_values(self):
        """Test profile enum values"""
        assert PermissionProfile.MINIMAL.value == "minimal"
        assert PermissionProfile.STANDARD.value == "standard"
        assert PermissionProfile.EXTENDED.value == "extended"
        assert PermissionProfile.ADMIN.value == "admin"
        assert PermissionProfile.CUSTOM.value == "custom"
    
    def test_profile_permissions_defined(self):
        """Test that all profiles have permission sets"""
        assert PermissionProfile.MINIMAL in PROFILE_PERMISSIONS
        assert PermissionProfile.STANDARD in PROFILE_PERMISSIONS
        assert PermissionProfile.EXTENDED in PROFILE_PERMISSIONS
        assert PermissionProfile.ADMIN in PROFILE_PERMISSIONS
    
    def test_minimal_profile(self):
        """Test minimal profile has minimum permissions"""
        perms = PROFILE_PERMISSIONS[PermissionProfile.MINIMAL]
        
        assert Permission.EXECUTE in perms
        assert Permission.CONFIG_READ in perms
        assert Permission.EVENT_SUBSCRIBE in perms
        
        # Should not have write permissions
        assert Permission.FILE_WRITE not in perms
        assert Permission.DATABASE_WRITE not in perms
    
    def test_standard_profile(self):
        """Test standard profile has typical permissions"""
        perms = PROFILE_PERMISSIONS[PermissionProfile.STANDARD]
        
        assert Permission.EXECUTE in perms
        assert Permission.FILE_READ in perms
        assert Permission.NETWORK_HTTP in perms
        assert Permission.DATABASE_READ in perms
        assert Permission.PLATFORM_SEND in perms
        
        # Should not have dangerous permissions
        assert Permission.SYSTEM_SHELL not in perms
        assert Permission.PLATFORM_ADMIN not in perms
    
    def test_extended_profile(self):
        """Test extended profile has more permissions"""
        perms = PROFILE_PERMISSIONS[PermissionProfile.EXTENDED]
        
        assert Permission.FILE_WRITE in perms
        assert Permission.DATABASE_WRITE in perms
        assert Permission.PLATFORM_MODERATE in perms
        assert Permission.RESOURCE_MEMORY_HIGH in perms
    
    def test_admin_profile(self):
        """Test admin profile has all permissions"""
        perms = PROFILE_PERMISSIONS[PermissionProfile.ADMIN]
        
        # Should have everything
        assert Permission.EXECUTE in perms
        assert Permission.SYSTEM_SHELL in perms
        assert Permission.PLATFORM_ADMIN in perms
        assert Permission.DATABASE_SCHEMA in perms
        assert len(perms) == len(list(Permission))
    
    def test_profile_hierarchy(self):
        """Test that profiles form a hierarchy"""
        minimal = PROFILE_PERMISSIONS[PermissionProfile.MINIMAL]
        standard = PROFILE_PERMISSIONS[PermissionProfile.STANDARD]
        extended = PROFILE_PERMISSIONS[PermissionProfile.EXTENDED]
        admin = PROFILE_PERMISSIONS[PermissionProfile.ADMIN]
        
        # Each level should include previous levels
        assert minimal.issubset(standard)
        assert standard.issubset(extended)
        assert extended.issubset(admin)


# ============================================================================
# PluginPermissions Tests
# ============================================================================

class TestPluginPermissions:
    """Test plugin permissions management"""
    
    def test_permissions_creation(self):
        """Test creating plugin permissions"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.STANDARD
        )
        
        assert perms.plugin_name == "test-plugin"
        assert perms.profile == PermissionProfile.STANDARD
        assert len(perms.granted) > 0
    
    def test_permissions_from_profile(self):
        """Test permissions initialized from profile"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.MINIMAL
        )
        
        # Should have minimal permissions
        assert Permission.EXECUTE in perms.granted
        assert Permission.CONFIG_READ in perms.granted
        
        # Should not have extended permissions
        assert Permission.FILE_WRITE not in perms.granted
    
    def test_has_permission(self):
        """Test checking single permission"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.STANDARD
        )
        
        assert perms.has_permission(Permission.EXECUTE) is True
        assert perms.has_permission(Permission.FILE_READ) is True
        assert perms.has_permission(Permission.SYSTEM_SHELL) is False
    
    def test_has_all(self):
        """Test checking multiple permissions (all)"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.STANDARD
        )
        
        # All present
        assert perms.has_all(
            Permission.EXECUTE,
            Permission.FILE_READ,
            Permission.NETWORK_HTTP
        ) is True
        
        # One missing
        assert perms.has_all(
            Permission.EXECUTE,
            Permission.SYSTEM_SHELL
        ) is False
    
    def test_has_any(self):
        """Test checking multiple permissions (any)"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.MINIMAL
        )
        
        # At least one present
        assert perms.has_any(
            Permission.EXECUTE,
            Permission.SYSTEM_SHELL
        ) is True
        
        # None present
        assert perms.has_any(
            Permission.FILE_WRITE,
            Permission.SYSTEM_SHELL
        ) is False
    
    def test_grant_permission(self):
        """Test granting permissions"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.MINIMAL
        )
        
        assert Permission.FILE_WRITE not in perms.granted
        
        perms.grant(Permission.FILE_WRITE)
        
        assert Permission.FILE_WRITE in perms.granted
    
    def test_grant_multiple_permissions(self):
        """Test granting multiple permissions at once"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.MINIMAL
        )
        
        perms.grant(
            Permission.FILE_WRITE,
            Permission.NETWORK_HTTP,
            Permission.DATABASE_WRITE
        )
        
        assert Permission.FILE_WRITE in perms.granted
        assert Permission.NETWORK_HTTP in perms.granted
        assert Permission.DATABASE_WRITE in perms.granted
    
    def test_revoke_permission(self):
        """Test revoking permissions"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.STANDARD
        )
        
        assert Permission.FILE_READ in perms.granted
        
        perms.revoke(Permission.FILE_READ)
        
        assert Permission.FILE_READ not in perms.granted
    
    def test_grant_profile(self):
        """Test granting entire profile"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.MINIMAL
        )
        
        assert Permission.FILE_WRITE not in perms.granted
        
        perms.grant_profile(PermissionProfile.EXTENDED)
        
        assert perms.profile == PermissionProfile.EXTENDED
        assert Permission.FILE_WRITE in perms.granted
        assert Permission.DATABASE_WRITE in perms.granted
    
    def test_check_and_log(self):
        """Test permission check with logging"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.MINIMAL
        )
        
        # Allowed permission
        result = perms.check_and_log(Permission.EXECUTE, "run plugin")
        assert result is True
        assert len(perms.denied_log) == 0
        
        # Denied permission
        result = perms.check_and_log(Permission.FILE_WRITE, "write file")
        assert result is False
        assert len(perms.denied_log) == 1
        assert perms.denied_log[0]["permission"] == "FILE_WRITE"
        assert perms.denied_log[0]["action"] == "write file"
    
    def test_get_granted_names(self):
        """Test getting permission names"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.MINIMAL
        )
        
        names = perms.get_granted_names()
        
        assert isinstance(names, list)
        assert "EXECUTE" in names
        assert "CONFIG_READ" in names
        assert names == sorted(names)  # Should be sorted
    
    def test_get_denied_count(self):
        """Test getting denied count"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.MINIMAL
        )
        
        assert perms.get_denied_count() == 0
        
        perms.check_and_log(Permission.FILE_WRITE, "test")
        perms.check_and_log(Permission.SYSTEM_SHELL, "test")
        
        assert perms.get_denied_count() == 2
    
    def test_clear_denied_log(self):
        """Test clearing denied log"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.MINIMAL
        )
        
        perms.check_and_log(Permission.FILE_WRITE, "test")
        assert len(perms.denied_log) > 0
        
        perms.clear_denied_log()
        assert len(perms.denied_log) == 0
    
    def test_to_dict(self):
        """Test serializing to dictionary"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.STANDARD
        )
        
        data = perms.to_dict()
        
        assert data["plugin_name"] == "test-plugin"
        assert data["profile"] == "standard"
        assert isinstance(data["granted"], list)
        assert "EXECUTE" in data["granted"]
    
    def test_from_dict(self):
        """Test deserializing from dictionary"""
        data = {
            "plugin_name": "test-plugin",
            "profile": "standard",
            "granted": ["EXECUTE", "FILE_READ", "NETWORK_HTTP"]
        }
        
        perms = PluginPermissions.from_dict(data)
        
        assert perms.plugin_name == "test-plugin"
        assert perms.profile == PermissionProfile.STANDARD
        assert Permission.EXECUTE in perms.granted
        assert Permission.FILE_READ in perms.granted
        assert Permission.NETWORK_HTTP in perms.granted
    
    def test_roundtrip_serialization(self):
        """Test serialization roundtrip"""
        original = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.EXTENDED
        )
        original.grant(Permission.SYSTEM_ENV)
        
        data = original.to_dict()
        restored = PluginPermissions.from_dict(data)
        
        assert restored.plugin_name == original.plugin_name
        assert restored.profile == original.profile
        assert restored.granted == original.granted


# ============================================================================
# PermissionValidator Tests
# ============================================================================

class TestPermissionValidator:
    """Test permission validation and enforcement"""
    
    def test_validator_creation(self):
        """Test creating validator"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.STANDARD
        )
        validator = PermissionValidator(perms)
        
        assert validator.permissions is perms
    
    def test_check_allowed(self):
        """Test checking allowed permission"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.STANDARD
        )
        validator = PermissionValidator(perms)
        
        result = validator.check(Permission.FILE_READ, "read file")
        assert result is True
    
    def test_check_denied(self):
        """Test checking denied permission"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.MINIMAL
        )
        validator = PermissionValidator(perms)
        
        result = validator.check(Permission.FILE_WRITE, "write file")
        assert result is False
        assert len(perms.denied_log) == 1
    
    def test_assert_permission_allowed(self):
        """Test asserting allowed permission"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.STANDARD
        )
        validator = PermissionValidator(perms)
        
        # Should not raise
        validator.assert_permission(Permission.FILE_READ, "read file")
    
    def test_assert_permission_denied(self):
        """Test asserting denied permission raises exception"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.MINIMAL
        )
        validator = PermissionValidator(perms)
        
        with pytest.raises(PermissionError) as exc_info:
            validator.assert_permission(Permission.FILE_WRITE, "write file")
        
        assert exc_info.value.plugin_name == "test-plugin"
        assert exc_info.value.permission == Permission.FILE_WRITE
        assert "write file" in str(exc_info.value)
    
    def test_require_decorator_allowed(self):
        """Test require decorator with allowed permission"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.STANDARD
        )
        validator = PermissionValidator(perms)
        
        @validator.require(Permission.FILE_READ, "read config")
        def load_config():
            return "config loaded"
        
        result = load_config()
        assert result == "config loaded"
    
    def test_require_decorator_denied(self):
        """Test require decorator with denied permission"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.MINIMAL
        )
        validator = PermissionValidator(perms)
        
        @validator.require(Permission.FILE_WRITE, "write config")
        def save_config():
            return "config saved"
        
        with pytest.raises(PermissionError):
            save_config()
    
    def test_require_any_decorator(self):
        """Test require_any decorator"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.STANDARD
        )
        validator = PermissionValidator(perms)
        
        @validator.require_any(
            Permission.FILE_READ,
            Permission.FILE_WRITE,
            action="access file"
        )
        def access_file():
            return "accessed"
        
        # Has FILE_READ, should succeed
        result = access_file()
        assert result == "accessed"
    
    def test_require_any_decorator_denied(self):
        """Test require_any decorator when all denied"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.MINIMAL
        )
        validator = PermissionValidator(perms)
        
        @validator.require_any(
            Permission.FILE_WRITE,
            Permission.SYSTEM_SHELL,
            action="dangerous action"
        )
        def dangerous_action():
            return "done"
        
        with pytest.raises(PermissionError):
            dangerous_action()
    
    def test_require_all_decorator(self):
        """Test require_all decorator"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.STANDARD
        )
        validator = PermissionValidator(perms)
        
        @validator.require_all(
            Permission.FILE_READ,
            Permission.NETWORK_HTTP,
            action="download file"
        )
        def download_file():
            return "downloaded"
        
        # Has both, should succeed
        result = download_file()
        assert result == "downloaded"
    
    def test_require_all_decorator_denied(self):
        """Test require_all decorator when one missing"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.STANDARD
        )
        validator = PermissionValidator(perms)
        
        @validator.require_all(
            Permission.FILE_READ,
            Permission.SYSTEM_SHELL,  # Don't have this
            action="execute script"
        )
        def execute_script():
            return "executed"
        
        with pytest.raises(PermissionError):
            execute_script()


# ============================================================================
# FileAccessPolicy Tests
# ============================================================================

class TestFileAccessPolicy:
    """Test file access policy"""
    
    def test_policy_creation(self):
        """Test creating file access policy"""
        policy = FileAccessPolicy()
        
        assert len(policy.allowed_paths) == 0
        assert len(policy.denied_paths) == 0
        assert len(policy.allowed_patterns) == 0
        assert len(policy.denied_patterns) == 0
    
    def test_add_allowed_path(self):
        """Test adding allowed path"""
        policy = FileAccessPolicy()
        path = Path("/tmp/test.txt")
        
        policy.add_allowed_path(path)
        
        assert path.resolve() in policy.allowed_paths
    
    def test_add_denied_path(self):
        """Test adding denied path"""
        policy = FileAccessPolicy()
        path = Path("/etc/passwd")
        
        policy.add_denied_path(path)
        
        assert path.resolve() in policy.denied_paths
    
    def test_is_allowed_explicit(self):
        """Test explicit path allow"""
        policy = FileAccessPolicy()
        allowed = Path("/tmp/allowed.txt")
        denied = Path("/tmp/denied.txt")
        
        policy.add_allowed_path(allowed)
        
        assert policy.is_allowed(allowed) is True
        assert policy.is_allowed(denied) is False
    
    def test_is_allowed_denied_priority(self):
        """Test that denials take priority"""
        policy = FileAccessPolicy()
        path = Path("/tmp/test.txt")
        
        policy.add_allowed_path(path)
        policy.add_denied_path(path)
        
        # Denial should override allow
        assert policy.is_allowed(path) is False
    
    def test_is_allowed_pattern(self):
        """Test pattern-based access"""
        policy = FileAccessPolicy()
        
        policy.add_allowed_pattern("*.txt")
        
        assert policy.is_allowed(Path("test.txt")) is True
        assert policy.is_allowed(Path("test.json")) is False
    
    def test_is_allowed_denied_pattern(self):
        """Test denied pattern"""
        policy = FileAccessPolicy()
        
        policy.add_allowed_pattern("*")  # Allow all
        policy.add_denied_pattern("*.secret")  # Except secrets
        
        assert policy.is_allowed(Path("test.txt")) is True
        assert policy.is_allowed(Path("test.secret")) is False


# ============================================================================
# Helper Function Tests
# ============================================================================

class TestHelperFunctions:
    """Test helper functions"""
    
    def test_create_restricted_permissions(self):
        """Test creating restricted permissions"""
        perms = create_restricted_permissions(
            "test-plugin",
            base_profile=PermissionProfile.MINIMAL,
            additional_permissions={Permission.FILE_READ, Permission.NETWORK_HTTP}
        )
        
        assert perms.plugin_name == "test-plugin"
        assert perms.profile == PermissionProfile.MINIMAL
        assert Permission.EXECUTE in perms.granted
        assert Permission.FILE_READ in perms.granted
        assert Permission.NETWORK_HTTP in perms.granted
    
    def test_create_restricted_permissions_with_file_policy(self):
        """Test creating permissions with file policy"""
        file_policy = FileAccessPolicy()
        file_policy.add_allowed_pattern("*.txt")
        
        perms = create_restricted_permissions(
            "test-plugin",
            file_policy=file_policy
        )
        
        retrieved_policy = get_file_policy(perms)
        assert retrieved_policy is file_policy
    
    def test_get_file_policy_none(self):
        """Test getting file policy when not set"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.MINIMAL
        )
        
        policy = get_file_policy(perms)
        assert policy is None
    
    def test_permission_summary(self):
        """Test generating permission summary"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.STANDARD
        )
        
        summary = permission_summary(perms)
        
        assert "test-plugin" in summary
        assert "standard" in summary
        assert "EXECUTE" in summary
        assert "FILE_READ" in summary
    
    def test_permission_summary_with_denials(self):
        """Test summary includes denial count"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.MINIMAL
        )
        
        perms.check_and_log(Permission.FILE_WRITE, "test")
        perms.check_and_log(Permission.SYSTEM_SHELL, "test")
        
        summary = permission_summary(perms)
        
        assert "Denied Attempts: 2" in summary


# ============================================================================
# Integration Tests
# ============================================================================

class TestPermissionIntegration:
    """Test permission system integration"""
    
    def test_full_permission_workflow(self):
        """Test complete permission workflow"""
        # Create permissions
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.STANDARD
        )
        
        # Create validator
        validator = PermissionValidator(perms)
        
        # Define protected function
        @validator.require(Permission.FILE_READ, "read config")
        def load_config():
            return {"key": "value"}
        
        # Should work
        config = load_config()
        assert config == {"key": "value"}
        
        # Define function requiring missing permission
        @validator.require(Permission.SYSTEM_SHELL, "run shell")
        def run_shell():
            return "executed"
        
        # Should fail
        with pytest.raises(PermissionError) as exc_info:
            run_shell()
        
        assert exc_info.value.plugin_name == "test-plugin"
        assert len(perms.denied_log) == 1
    
    def test_dynamic_permission_changes(self):
        """Test changing permissions at runtime"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.MINIMAL
        )
        validator = PermissionValidator(perms)
        
        @validator.require(Permission.FILE_WRITE, "write file")
        def write_file():
            return "written"
        
        # Initially fails
        with pytest.raises(PermissionError):
            write_file()
        
        # Grant permission
        perms.grant(Permission.FILE_WRITE)
        
        # Now succeeds
        result = write_file()
        assert result == "written"
    
    def test_profile_upgrade(self):
        """Test upgrading permission profile"""
        perms = PluginPermissions(
            plugin_name="test-plugin",
            profile=PermissionProfile.MINIMAL
        )
        
        # Check initial permissions
        assert Permission.FILE_WRITE not in perms.granted
        assert Permission.DATABASE_WRITE not in perms.granted
        
        # Upgrade to extended
        perms.grant_profile(PermissionProfile.EXTENDED)
        
        # Should now have extended permissions
        assert Permission.FILE_WRITE in perms.granted
        assert Permission.DATABASE_WRITE in perms.granted
        assert perms.profile == PermissionProfile.EXTENDED
