#!/usr/bin/env python3
"""
Conversation Memory Data Backup and Analysis Script
Part of Phase 1: Foundation & Safety

This script:
1. Creates complete backup of conversation data
2. Analyzes conversation ID patterns
3. Maps data distribution across different ID formats
4. Validates data integrity before migration
"""

import sqlite3
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple
from collections import defaultdict

class ConversationBackupManager:
    """Manages conversation data backup and analysis for migration."""
    
    def __init__(self, db_path: str = "app/memory/unified.db"):
        self.db_path = Path(db_path)
        self.backup_dir = Path("migration_backups")
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.analysis_results = {}
        
    def create_backup_directory(self):
        """Create backup directory structure."""
        backup_path = self.backup_dir / f"backup_{self.timestamp}"
        backup_path.mkdir(parents=True, exist_ok=True)
        return backup_path
        
    def backup_database(self) -> Path:
        """Create complete database backup."""
        print("🔄 Creating database backup...")
        backup_path = self.create_backup_directory()
        backup_db_path = backup_path / "unified.db.backup"
        
        # Copy database file
        shutil.copy2(self.db_path, backup_db_path)
        
        # Create SQL dump as well
        dump_path = backup_path / "unified_dump.sql"
        with open(dump_path, 'w') as f:
            conn = sqlite3.connect(str(self.db_path))
            for line in conn.iterdump():
                f.write(f"{line}\n")
            conn.close()
            
        print(f"✅ Database backed up to: {backup_path}")
        return backup_path
        
    def analyze_conversation_patterns(self) -> Dict[str, Any]:
        """Analyze conversation ID patterns in the database."""
        print("🔍 Analyzing conversation patterns...")
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Get all conversation data
        cursor.execute("""
            SELECT conversation_id, role, content, timestamp, user_id, created_at
            FROM conversations 
            ORDER BY conversation_id, created_at
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        # Analyze patterns
        conversation_stats = defaultdict(lambda: {
            'message_count': 0,
            'user_messages': 0,
            'assistant_messages': 0,
            'users': set(),
            'first_message': None,
            'last_message': None,
            'id_format': 'unknown'
        })
        
        id_format_patterns = {
            'simple_project': [],      # just project slug
            'project_user': [],        # project:user format
            'other': []               # any other format
        }
        
        for row in rows:
            conversation_id, role, content, timestamp, user_id, created_at = row
            
            # Update conversation stats
            stats = conversation_stats[conversation_id]
            stats['message_count'] += 1
            stats['users'].add(user_id)
            
            if role == 'user':
                stats['user_messages'] += 1
            elif role == 'assistant':
                stats['assistant_messages'] += 1
                
            if stats['first_message'] is None:
                stats['first_message'] = created_at
            stats['last_message'] = created_at
            
            # Analyze ID format
            if ':' in conversation_id:
                stats['id_format'] = 'project_user'
                if conversation_id not in id_format_patterns['project_user']:
                    id_format_patterns['project_user'].append(conversation_id)
            elif conversation_id.count('-') >= 1:  # Simple project slug format
                stats['id_format'] = 'simple_project'
                if conversation_id not in id_format_patterns['simple_project']:
                    id_format_patterns['simple_project'].append(conversation_id)
            else:
                stats['id_format'] = 'other'
                if conversation_id not in id_format_patterns['other']:
                    id_format_patterns['other'].append(conversation_id)
        
        # Convert sets to lists for JSON serialization
        for conv_id in conversation_stats:
            conversation_stats[conv_id]['users'] = list(conversation_stats[conv_id]['users'])
            
        analysis = {
            'total_conversations': len(conversation_stats),
            'total_messages': sum(row[0] for row in [cursor.execute("SELECT COUNT(*) FROM conversations").fetchone() for cursor in [sqlite3.connect(str(self.db_path)).cursor()]]),
            'conversation_details': dict(conversation_stats),
            'id_format_patterns': id_format_patterns,
            'format_distribution': {
                'simple_project': len(id_format_patterns['simple_project']),
                'project_user': len(id_format_patterns['project_user']), 
                'other': len(id_format_patterns['other'])
            }
        }
        
        self.analysis_results = analysis
        print(f"✅ Analysis complete:")
        print(f"   📊 Total conversations: {analysis['total_conversations']}")
        print(f"   💬 Total messages: {analysis['total_messages']}")
        print(f"   📋 ID Formats:")
        print(f"      - Simple project: {analysis['format_distribution']['simple_project']}")
        print(f"      - Project:user: {analysis['format_distribution']['project_user']}")
        print(f"      - Other: {analysis['format_distribution']['other']}")
        
        return analysis
        
    def save_analysis_report(self, backup_path: Path):
        """Save detailed analysis report."""
        report_path = backup_path / "conversation_analysis.json"
        
        with open(report_path, 'w') as f:
            json.dump(self.analysis_results, f, indent=2, default=str)
            
        # Create human-readable summary
        summary_path = backup_path / "analysis_summary.md"
        with open(summary_path, 'w') as f:
            f.write(f"# Conversation Memory Analysis Report\n\n")
            f.write(f"**Generated**: {datetime.now().isoformat()}\n\n")
            f.write(f"## Summary\n\n")
            f.write(f"- **Total Conversations**: {self.analysis_results['total_conversations']}\n")
            f.write(f"- **Total Messages**: {self.analysis_results['total_messages']}\n\n")
            
            f.write(f"## Conversation ID Format Distribution\n\n")
            for format_type, count in self.analysis_results['format_distribution'].items():
                f.write(f"- **{format_type.replace('_', ' ').title()}**: {count} conversations\n")
                
            f.write(f"\n## Detailed Conversation Breakdown\n\n")
            for conv_id, details in self.analysis_results['conversation_details'].items():
                f.write(f"### `{conv_id}`\n")
                f.write(f"- **Format**: {details['id_format']}\n")
                f.write(f"- **Messages**: {details['message_count']} ({details['user_messages']} user, {details['assistant_messages']} assistant)\n")
                f.write(f"- **Users**: {', '.join(details['users'])}\n")
                f.write(f"- **Period**: {details['first_message']} to {details['last_message']}\n\n")
                
        print(f"✅ Analysis report saved to: {report_path}")
        return report_path
        
    def validate_data_integrity(self) -> Dict[str, Any]:
        """Validate current data integrity before migration."""
        print("🔍 Validating data integrity...")
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        validation_results = {
            'total_messages': 0,
            'orphaned_messages': 0,
            'invalid_roles': 0,
            'empty_content': 0,
            'missing_timestamps': 0,
            'duplicate_messages': 0,
            'valid_messages': 0
        }
        
        # Check total messages
        cursor.execute("SELECT COUNT(*) FROM conversations")
        validation_results['total_messages'] = cursor.fetchone()[0]
        
        # Check for invalid roles
        cursor.execute("SELECT COUNT(*) FROM conversations WHERE role NOT IN ('user', 'assistant', 'system')")
        validation_results['invalid_roles'] = cursor.fetchone()[0]
        
        # Check for empty content
        cursor.execute("SELECT COUNT(*) FROM conversations WHERE content IS NULL OR content = ''")
        validation_results['empty_content'] = cursor.fetchone()[0]
        
        # Check for missing timestamps
        cursor.execute("SELECT COUNT(*) FROM conversations WHERE created_at IS NULL")
        validation_results['missing_timestamps'] = cursor.fetchone()[0]
        
        # Check for potential duplicates (same content, role, conversation_id)
        cursor.execute("""
            SELECT conversation_id, role, content, COUNT(*) as count
            FROM conversations 
            GROUP BY conversation_id, role, content
            HAVING COUNT(*) > 1
        """)
        duplicates = cursor.fetchall()
        validation_results['duplicate_messages'] = len(duplicates)
        
        # Calculate valid messages
        validation_results['valid_messages'] = (
            validation_results['total_messages'] 
            - validation_results['invalid_roles'] 
            - validation_results['empty_content']
            - validation_results['missing_timestamps']
        )
        
        conn.close()
        
        print(f"✅ Data integrity validation complete:")
        print(f"   📊 Total messages: {validation_results['total_messages']}")
        print(f"   ✅ Valid messages: {validation_results['valid_messages']}")
        print(f"   ⚠️  Issues found:")
        print(f"      - Invalid roles: {validation_results['invalid_roles']}")
        print(f"      - Empty content: {validation_results['empty_content']}")
        print(f"      - Missing timestamps: {validation_results['missing_timestamps']}")
        print(f"      - Potential duplicates: {validation_results['duplicate_messages']}")
        
        return validation_results
        
    def run_complete_backup(self):
        """Run complete backup and analysis process."""
        print("🚀 Starting Phase 1: Foundation & Safety - Data Backup")
        print("=" * 60)
        
        # Create backup
        backup_path = self.backup_database()
        
        # Analyze patterns
        analysis = self.analyze_conversation_patterns()
        
        # Save analysis report
        self.save_analysis_report(backup_path)
        
        # Validate integrity
        integrity = self.validate_data_integrity()
        
        # Save integrity report
        integrity_path = backup_path / "data_integrity.json"
        with open(integrity_path, 'w') as f:
            json.dump(integrity, f, indent=2)
            
        print("\n" + "=" * 60)
        print("✅ Phase 1 Data Backup Complete!")
        print(f"📁 Backup location: {backup_path}")
        print(f"📊 Analysis: {len(analysis['conversation_details'])} conversations analyzed")
        print(f"🔍 Integrity: {integrity['valid_messages']}/{integrity['total_messages']} valid messages")
        print("=" * 60)
        
        return backup_path, analysis, integrity

if __name__ == "__main__":
    backup_manager = ConversationBackupManager()
    backup_manager.run_complete_backup()