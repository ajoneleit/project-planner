"""
Feature Flags System - Phase 1: Safety Infrastructure
Part of the unified conversation memory architecture migration.

This module provides:
1. Safe feature rollout controls
2. Migration phase gating  
3. Rollback capabilities
4. A/B testing support for memory systems
"""

import os
import json
import asyncio
import hashlib
from typing import Dict, Any, Optional, Set
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class MigrationPhase(Enum):
    """Migration phases for conversation memory system."""
    PRE_MIGRATION = "pre_migration"           # Legacy system only
    PHASE_1_SAFETY = "phase_1_safety"        # Foundation & backup
    PHASE_2_UNIFIED = "phase_2_unified"       # Dual system with unified primary
    PHASE_3_MIGRATION = "phase_3_migration"   # Active data migration
    PHASE_4_VALIDATION = "phase_4_validation" # Testing & validation
    PHASE_5_CLEANUP = "phase_5_cleanup"       # Legacy system removal
    POST_MIGRATION = "post_migration"         # Unified system only

@dataclass
class FeatureFlag:
    """Configuration for a feature flag."""
    name: str
    enabled: bool = False
    rollout_percentage: float = 0.0  # 0.0 to 100.0
    migration_phase: Optional[MigrationPhase] = None
    description: str = ""
    
    # Safety controls
    max_rollout_percentage: float = 100.0
    requires_confirmation: bool = False
    
    # Metadata
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    created_by: str = "system"

class FeatureFlagManager:
    """
    Feature flag management system for safe migration rollout.
    
    Supports:
    - Gradual feature rollout with percentage controls
    - Migration phase gating
    - Environment-specific configurations
    - Safe rollback capabilities
    """
    
    def __init__(self, config_path: str = "app/config/feature_flags.json"):
        self.config_path = Path(config_path)
        self._flags: Dict[str, FeatureFlag] = {}
        self._lock = asyncio.Lock()
        self._current_phase = MigrationPhase.PRE_MIGRATION
        self._user_rollout_cache: Dict[str, Set[str]] = {}  # user_id -> enabled features
        
        # Default migration flags
        self._default_flags = {
            # Phase 1: Foundation & Safety
            "conversation_id_manager": FeatureFlag(
                name="conversation_id_manager",
                enabled=True,
                rollout_percentage=100.0,
                migration_phase=MigrationPhase.PHASE_1_SAFETY,
                description="Enable unified conversation ID management system"
            ),
            "memory_migration_logging": FeatureFlag(
                name="memory_migration_logging",
                enabled=True,
                rollout_percentage=100.0,
                migration_phase=MigrationPhase.PHASE_1_SAFETY,
                description="Enable detailed logging for memory system migration"
            ),
            "data_integrity_validation": FeatureFlag(
                name="data_integrity_validation",
                enabled=True,
                rollout_percentage=100.0,
                migration_phase=MigrationPhase.PHASE_1_SAFETY,
                description="Enable data integrity checks during operations"
            ),
            
            # Phase 2: Unified System
            "unified_memory_primary": FeatureFlag(
                name="unified_memory_primary",
                enabled=False,
                rollout_percentage=0.0,
                migration_phase=MigrationPhase.PHASE_2_UNIFIED,
                description="Use unified memory as primary system (dual-write mode)",
                requires_confirmation=True
            ),
            "compatibility_layer_active": FeatureFlag(
                name="compatibility_layer_active",
                enabled=True,
                rollout_percentage=100.0,
                migration_phase=MigrationPhase.PHASE_2_UNIFIED,
                description="Keep compatibility layer active during migration"
            ),
            
            # Phase 3: Active Migration
            "active_data_migration": FeatureFlag(
                name="active_data_migration",
                enabled=False,
                rollout_percentage=0.0,
                migration_phase=MigrationPhase.PHASE_3_MIGRATION,
                description="Enable active migration of conversation data",
                requires_confirmation=True
            ),
            "legacy_system_read_only": FeatureFlag(
                name="legacy_system_read_only",
                enabled=False,
                rollout_percentage=0.0,
                migration_phase=MigrationPhase.PHASE_3_MIGRATION,
                description="Make legacy system read-only during migration"
            ),
            
            # Phase 4: Validation
            "migration_validation": FeatureFlag(
                name="migration_validation",
                enabled=False,
                rollout_percentage=0.0,
                migration_phase=MigrationPhase.PHASE_4_VALIDATION,
                description="Enable comprehensive migration validation"
            ),
            
            # Phase 5: Cleanup
            "legacy_system_disabled": FeatureFlag(
                name="legacy_system_disabled",
                enabled=False,
                rollout_percentage=0.0,
                migration_phase=MigrationPhase.PHASE_5_CLEANUP,
                description="Disable legacy memory system completely",
                requires_confirmation=True
            )
        }
    
    async def initialize(self) -> bool:
        """Initialize feature flag system."""
        async with self._lock:
            try:
                # Create config directory
                self.config_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Load existing config or create default
                if self.config_path.exists():
                    await self._load_config()
                else:
                    await self._create_default_config()
                
                logger.info(f"Feature flag system initialized with {len(self._flags)} flags")
                return True
                
            except Exception as e:
                logger.error(f"Failed to initialize feature flags: {e}")
                return False
    
    async def _load_config(self):
        """Load feature flags from config file."""
        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
            
            # Load current phase
            self._current_phase = MigrationPhase(data.get('current_phase', MigrationPhase.PRE_MIGRATION.value))
            
            # Load flags
            flags_data = data.get('flags', {})
            self._flags = {}
            
            for flag_name, flag_data in flags_data.items():
                # Convert migration_phase back to enum
                phase_str = flag_data.get('migration_phase')
                phase = MigrationPhase(phase_str) if phase_str else None
                flag_data['migration_phase'] = phase
                
                self._flags[flag_name] = FeatureFlag(**flag_data)
            
            # Merge in any new default flags
            for name, default_flag in self._default_flags.items():
                if name not in self._flags:
                    self._flags[name] = default_flag
                    
        except Exception as e:
            logger.error(f"Error loading feature flags config: {e}")
            # Fall back to defaults
            self._flags = self._default_flags.copy()
    
    async def _create_default_config(self):
        """Create default feature flags configuration."""
        self._flags = self._default_flags.copy()
        await self._save_config()
        logger.info("Created default feature flags configuration")
    
    async def _save_config(self):
        """Save current feature flags to config file."""
        try:
            data = {
                'current_phase': self._current_phase.value,
                'flags': {}
            }
            
            for name, flag in self._flags.items():
                flag_dict = asdict(flag)
                # Convert enum to string for JSON serialization
                if flag_dict['migration_phase']:
                    flag_dict['migration_phase'] = flag_dict['migration_phase'].value
                data['flags'][name] = flag_dict
            
            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Error saving feature flags config: {e}")
    
    def is_enabled(self, flag_name: str, user_id: str = "anonymous") -> bool:
        """
        Check if a feature flag is enabled for a specific user.
        
        Args:
            flag_name: Name of the feature flag
            user_id: User identifier for rollout percentage calculation
            
        Returns:
            True if the feature is enabled for this user
        """
        try:
            flag = self._flags.get(flag_name)
            if not flag:
                logger.warning(f"Feature flag '{flag_name}' not found")
                return False
            
            # Check if flag is globally disabled
            if not flag.enabled:
                return False
            
            # Check migration phase compatibility
            if flag.migration_phase and not self._is_phase_active(flag.migration_phase):
                return False
            
            # Check rollout percentage
            if flag.rollout_percentage >= 100.0:
                return True
            elif flag.rollout_percentage <= 0.0:
                return False
            
            # Use consistent hash-based rollout
            return self._is_user_in_rollout(user_id, flag_name, flag.rollout_percentage)
            
        except Exception as e:
            logger.error(f"Error checking feature flag '{flag_name}': {e}")
            return False
    
    def _is_phase_active(self, required_phase: MigrationPhase) -> bool:
        """Check if a migration phase is currently active."""
        phase_order = list(MigrationPhase)
        current_index = phase_order.index(self._current_phase)
        required_index = phase_order.index(required_phase)
        
        # Phase is active if current phase is >= required phase
        return current_index >= required_index
    
    def _is_user_in_rollout(self, user_id: str, flag_name: str, percentage: float) -> bool:
        """Determine if user is included in rollout percentage using consistent hashing."""
        # Create a consistent hash from user_id + flag_name
        combined = f"{user_id}:{flag_name}"
        
        # Use SHA256 for stable, consistent hashing across process restarts
        hash_bytes = hashlib.sha256(combined.encode('utf-8')).digest()
        # Take the first 4 bytes and interpret as an integer
        hash_int = int.from_bytes(hash_bytes[:4], 'big')
        hash_value = hash_int % 10000  # 0-9999
        
        threshold = int(percentage * 100)  # Convert percentage to 0-10000 range
        
        return hash_value < threshold
    
    async def set_migration_phase(self, phase: MigrationPhase) -> bool:
        """Set the current migration phase."""
        async with self._lock:
            try:
                old_phase = self._current_phase
                self._current_phase = phase
                await self._save_config()
                
                logger.info(f"Migration phase changed from {old_phase.value} to {phase.value}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to set migration phase: {e}")
                return False
    
    async def enable_flag(self, flag_name: str, rollout_percentage: float = 100.0) -> bool:
        """Enable a feature flag with optional rollout percentage."""
        async with self._lock:
            try:
                if flag_name not in self._flags:
                    logger.error(f"Feature flag '{flag_name}' not found")
                    return False
                
                flag = self._flags[flag_name]
                
                # Safety check for flags requiring confirmation
                if flag.requires_confirmation and rollout_percentage > 50.0:
                    logger.warning(f"Flag '{flag_name}' requires confirmation for rollout > 50%")
                    return False
                
                flag.enabled = True
                flag.rollout_percentage = min(rollout_percentage, flag.max_rollout_percentage)
                
                await self._save_config()
                logger.info(f"Enabled flag '{flag_name}' with {flag.rollout_percentage}% rollout")
                return True
                
            except Exception as e:
                logger.error(f"Failed to enable flag '{flag_name}': {e}")
                return False
    
    async def disable_flag(self, flag_name: str) -> bool:
        """Disable a feature flag."""
        async with self._lock:
            try:
                if flag_name not in self._flags:
                    logger.error(f"Feature flag '{flag_name}' not found")
                    return False
                
                self._flags[flag_name].enabled = False
                self._flags[flag_name].rollout_percentage = 0.0
                
                await self._save_config()
                logger.info(f"Disabled flag '{flag_name}'")
                return True
                
            except Exception as e:
                logger.error(f"Failed to disable flag '{flag_name}': {e}")
                return False
    
    def get_flag_status(self, flag_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed status of a feature flag."""
        flag = self._flags.get(flag_name)
        if not flag:
            return None
        
        return {
            "name": flag.name,
            "enabled": flag.enabled,
            "rollout_percentage": flag.rollout_percentage,
            "migration_phase": flag.migration_phase.value if flag.migration_phase else None,
            "phase_active": self._is_phase_active(flag.migration_phase) if flag.migration_phase else True,
            "description": flag.description,
            "requires_confirmation": flag.requires_confirmation
        }
    
    def list_active_flags(self, user_id: str = "anonymous") -> Dict[str, bool]:
        """List all flags and their status for a specific user."""
        return {
            name: self.is_enabled(name, user_id)
            for name in self._flags.keys()
        }


# === Global Instance Management ===

_feature_flags: Optional[FeatureFlagManager] = None
_flags_lock = asyncio.Lock()

async def get_feature_flags() -> FeatureFlagManager:
    """Get singleton instance of feature flag manager."""
    global _feature_flags
    
    async with _flags_lock:
        if _feature_flags is None:
            _feature_flags = FeatureFlagManager()
            await _feature_flags.initialize()
        return _feature_flags

async def is_feature_enabled(flag_name: str, user_id: str = "anonymous") -> bool:
    """Convenience function to check if a feature is enabled."""
    flags = await get_feature_flags()
    return flags.is_enabled(flag_name, user_id)

async def set_migration_phase(phase: MigrationPhase) -> bool:
    """Convenience function to set migration phase."""
    flags = await get_feature_flags()
    return await flags.set_migration_phase(phase)