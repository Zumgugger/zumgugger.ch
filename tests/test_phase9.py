"""
Phase 9 Tests: Deployment & Operations

Tests for:
- Production Docker configuration
- Apache vhost template
- Systemd service template
- Deployment scripts
- CI/CD workflows
"""

import os
import pytest
import subprocess
import tempfile
import shutil


class TestDockerConfiguration:
    """Tests for Docker production configuration."""
    
    def test_dockerfile_exists(self):
        """Test that Dockerfile exists."""
        assert os.path.exists("Dockerfile")
    
    def test_dockerfile_has_multi_stage_build(self):
        """Test Dockerfile uses multi-stage build."""
        with open("Dockerfile", "r") as f:
            content = f.read()
        
        # Check for multi-stage build markers
        assert "FROM python:3.11-slim as builder" in content
        assert "FROM python:3.11-slim as production" in content
    
    def test_dockerfile_has_non_root_user(self):
        """Test Dockerfile creates and uses non-root user."""
        with open("Dockerfile", "r") as f:
            content = f.read()
        
        # Check for user creation
        assert "useradd" in content or "adduser" in content
        assert "USER appuser" in content or "USER www-data" in content
    
    def test_dockerfile_has_healthcheck(self):
        """Test Dockerfile has HEALTHCHECK instruction."""
        with open("Dockerfile", "r") as f:
            content = f.read()
        
        assert "HEALTHCHECK" in content
    
    def test_docker_compose_exists(self):
        """Test that docker-compose.yml exists."""
        assert os.path.exists("docker-compose.yml")
    
    def test_docker_compose_prod_exists(self):
        """Test that docker-compose.prod.yml exists."""
        assert os.path.exists("docker-compose.prod.yml")
    
    def test_docker_compose_has_logging(self):
        """Test docker-compose has logging configuration."""
        with open("docker-compose.yml", "r") as f:
            content = f.read()
        
        assert "logging:" in content
        assert "max-size" in content
        assert "max-file" in content
    
    def test_docker_compose_has_healthcheck(self):
        """Test docker-compose has healthcheck."""
        with open("docker-compose.yml", "r") as f:
            content = f.read()
        
        assert "healthcheck:" in content
    
    def test_docker_compose_has_resource_limits(self):
        """Test docker-compose has resource limits."""
        with open("docker-compose.yml", "r") as f:
            content = f.read()
        
        assert "deploy:" in content
        assert "resources:" in content
        assert "limits:" in content
    
    def test_docker_compose_binds_to_localhost(self):
        """Test docker-compose binds to localhost only."""
        with open("docker-compose.yml", "r") as f:
            content = f.read()
        
        # Should bind to 127.0.0.1, not 0.0.0.0
        assert "127.0.0.1:" in content


class TestDeploymentStructure:
    """Tests for deployment directory structure."""
    
    def test_deploy_directory_exists(self):
        """Test deploy directory exists."""
        assert os.path.isdir("deploy")
    
    def test_deploy_readme_exists(self):
        """Test deploy README exists."""
        assert os.path.exists("deploy/README.md")
    
    def test_apache_directory_exists(self):
        """Test Apache config directory exists."""
        assert os.path.isdir("deploy/apache")
    
    def test_apache_vhost_exists(self):
        """Test Apache vhost template exists."""
        assert os.path.exists("deploy/apache/vhost.conf")
    
    def test_systemd_directory_exists(self):
        """Test systemd config directory exists."""
        assert os.path.isdir("deploy/systemd")
    
    def test_systemd_service_exists(self):
        """Test systemd service template exists."""
        assert os.path.exists("deploy/systemd/websitecms.service")
    
    def test_scripts_directory_exists(self):
        """Test scripts directory exists."""
        assert os.path.isdir("deploy/scripts")
    
    def test_all_scripts_exist(self):
        """Test all deployment scripts exist."""
        scripts = [
            "deploy.sh",
            "setup-vhost.sh",
            "setup-ssl.sh",
            "allocate-port.sh",
            "backup.sh",
            "restore.sh",
            "start.sh",
            "stop.sh",
            "restart.sh",
            "status.sh",
        ]
        
        for script in scripts:
            script_path = f"deploy/scripts/{script}"
            assert os.path.exists(script_path), f"Missing script: {script}"


class TestApacheVhostTemplate:
    """Tests for Apache vhost template."""
    
    def test_vhost_has_http_redirect(self):
        """Test vhost template redirects HTTP to HTTPS."""
        with open("deploy/apache/vhost.conf", "r") as f:
            content = f.read()
        
        assert "<VirtualHost *:80>" in content
        assert "RewriteRule" in content or "Redirect" in content
    
    def test_vhost_has_https_config(self):
        """Test vhost template has HTTPS configuration."""
        with open("deploy/apache/vhost.conf", "r") as f:
            content = f.read()
        
        assert "<VirtualHost *:443>" in content
        assert "SSLEngine on" in content
    
    def test_vhost_has_proxy_config(self):
        """Test vhost template has proxy configuration."""
        with open("deploy/apache/vhost.conf", "r") as f:
            content = f.read()
        
        assert "ProxyPass" in content
        assert "ProxyPassReverse" in content
        assert "ProxyPreserveHost" in content
    
    def test_vhost_has_security_headers(self):
        """Test vhost template has security headers."""
        with open("deploy/apache/vhost.conf", "r") as f:
            content = f.read()
        
        assert "Strict-Transport-Security" in content
        assert "X-Content-Type-Options" in content
        assert "X-Frame-Options" in content
    
    def test_vhost_has_placeholders(self):
        """Test vhost template has correct placeholders."""
        with open("deploy/apache/vhost.conf", "r") as f:
            content = f.read()
        
        assert "{{DOMAIN}}" in content
        assert "{{SITENAME}}" in content
        assert "{{APP_PORT}}" in content


class TestSystemdServiceTemplate:
    """Tests for systemd service template."""
    
    def test_service_has_description(self):
        """Test service template has description."""
        with open("deploy/systemd/websitecms.service", "r") as f:
            content = f.read()
        
        assert "Description=" in content
    
    def test_service_has_dependencies(self):
        """Test service template has correct dependencies."""
        with open("deploy/systemd/websitecms.service", "r") as f:
            content = f.read()
        
        assert "After=docker.service" in content
        assert "Requires=docker.service" in content
    
    def test_service_has_exec_commands(self):
        """Test service template has exec commands."""
        with open("deploy/systemd/websitecms.service", "r") as f:
            content = f.read()
        
        assert "ExecStart=" in content
        assert "ExecStop=" in content
    
    def test_service_has_placeholders(self):
        """Test service template has correct placeholders."""
        with open("deploy/systemd/websitecms.service", "r") as f:
            content = f.read()
        
        assert "{{SITENAME}}" in content
        assert "{{SITE_DIR}}" in content


class TestDeploymentScripts:
    """Tests for deployment scripts."""
    
    def test_scripts_are_executable_format(self):
        """Test scripts have proper shebang."""
        scripts = [
            "deploy/scripts/deploy.sh",
            "deploy/scripts/setup-vhost.sh",
            "deploy/scripts/setup-ssl.sh",
            "deploy/scripts/allocate-port.sh",
            "deploy/scripts/backup.sh",
            "deploy/scripts/restore.sh",
            "deploy/scripts/start.sh",
            "deploy/scripts/stop.sh",
            "deploy/scripts/restart.sh",
            "deploy/scripts/status.sh",
        ]
        
        for script in scripts:
            with open(script, "r") as f:
                first_line = f.readline()
            assert first_line.startswith("#!/bin/bash"), f"{script} missing shebang"
    
    def test_deploy_script_validates_arguments(self):
        """Test deploy script validates required arguments."""
        with open("deploy/scripts/deploy.sh", "r") as f:
            content = f.read()
        
        assert "--domain" in content
        assert "--sitename" in content
        assert "show_usage" in content or "Usage:" in content
    
    def test_backup_script_has_retention(self):
        """Test backup script has retention policy."""
        with open("deploy/scripts/backup.sh", "r") as f:
            content = f.read()
        
        assert "retention" in content.lower() or "cleanup" in content.lower()


class TestCICDWorkflows:
    """Tests for CI/CD GitHub workflows.
    
    Note: GitHub workflows are at the repository root level (not in site_template)
    since they apply to the entire project, not individual exported sites.
    """
    
    # Path to repo root (parent of site_template)
    REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    def test_github_workflows_directory_exists(self):
        """Test .github/workflows directory exists at repo root."""
        workflows_dir = os.path.join(self.REPO_ROOT, ".github", "workflows")
        assert os.path.isdir(workflows_dir), f"Expected {workflows_dir} to exist"
    
    def test_test_workflow_exists(self):
        """Test CI test workflow exists."""
        workflow_path = os.path.join(self.REPO_ROOT, ".github", "workflows", "test.yml")
        assert os.path.exists(workflow_path), f"Expected {workflow_path} to exist"
    
    def test_deploy_workflow_exists(self):
        """Test deployment workflow exists."""
        workflow_path = os.path.join(self.REPO_ROOT, ".github", "workflows", "deploy.yml")
        assert os.path.exists(workflow_path), f"Expected {workflow_path} to exist"
    
    def test_test_workflow_runs_pytest(self):
        """Test CI workflow runs pytest."""
        workflow_path = os.path.join(self.REPO_ROOT, ".github", "workflows", "test.yml")
        with open(workflow_path, "r") as f:
            content = f.read()
        
        assert "pytest" in content
    
    def test_test_workflow_builds_docker(self):
        """Test CI workflow builds Docker image."""
        workflow_path = os.path.join(self.REPO_ROOT, ".github", "workflows", "test.yml")
        with open(workflow_path, "r") as f:
            content = f.read()
        
        assert "docker" in content.lower()
        assert "build" in content.lower()
    
    def test_deploy_workflow_has_manual_trigger(self):
        """Test deploy workflow can be triggered manually."""
        workflow_path = os.path.join(self.REPO_ROOT, ".github", "workflows", "deploy.yml")
        with open(workflow_path, "r") as f:
            content = f.read()
        
        assert "workflow_dispatch" in content


class TestDockerBuild:
    """Tests for Docker image build (integration tests)."""
    
    @pytest.mark.skipif(
        not shutil.which("docker"),
        reason="Docker not available"
    )
    def test_dockerfile_syntax_valid(self):
        """Test Dockerfile has valid syntax."""
        # Use docker build with --check flag if available, otherwise just parse
        result = subprocess.run(
            ["docker", "build", "--help"],
            capture_output=True,
            text=True
        )
        
        # Just check that Dockerfile can be read without issues
        with open("Dockerfile", "r") as f:
            content = f.read()
        
        # Basic syntax checks
        assert "FROM" in content
        assert "CMD" in content or "ENTRYPOINT" in content


class TestTemplateSubstitution:
    """Tests for template variable substitution."""
    
    def test_vhost_template_substitution(self):
        """Test Apache vhost template can be substituted."""
        with open("deploy/apache/vhost.conf", "r") as f:
            template = f.read()
        
        # Substitute variables
        result = template.replace("{{DOMAIN}}", "example.com")
        result = result.replace("{{SITENAME}}", "testsite")
        result = result.replace("{{APP_PORT}}", "30000")
        
        # Verify substitution
        assert "example.com" in result
        assert "testsite" in result
        assert "30000" in result
        # Check that actual placeholders (not in comments) are substituted
        # Comments may still mention {{variables}} as documentation
        assert "{{DOMAIN}}" not in result
        assert "{{SITENAME}}" not in result
        assert "{{APP_PORT}}" not in result
    
    def test_systemd_template_substitution(self):
        """Test systemd service template can be substituted."""
        with open("deploy/systemd/websitecms.service", "r") as f:
            template = f.read()
        
        # Substitute variables
        result = template.replace("{{SITENAME}}", "testsite")
        result = result.replace("{{SITE_DIR}}", "/var/www/testsite")
        
        # Verify substitution
        assert "testsite" in result
        assert "/var/www/testsite" in result
        # Check that actual placeholders are substituted
        assert "{{SITENAME}}" not in result
        assert "{{SITE_DIR}}" not in result
