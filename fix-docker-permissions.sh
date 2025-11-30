#!/bin/bash
# Fix Docker permissions for snap installation

echo "Setting up Docker permissions for snap installation..."

# Create docker group if it doesn't exist
if ! getent group docker > /dev/null 2>&1; then
    echo "Creating docker group..."
    sudo groupadd docker
fi

# Add current user to docker group
echo "Adding $USER to docker group..."
sudo usermod -aG docker $USER

# Change ownership of docker socket
echo "Updating docker socket permissions..."
sudo chown root:docker /var/run/docker.sock

# Fix socket permissions
sudo chmod 660 /var/run/docker.sock

echo ""
echo "✓ Docker permissions configured!"
echo ""
echo "IMPORTANT: Run this command to apply the group changes:"
echo "  newgrp docker"
echo ""
echo "Or log out and log back in for changes to take effect."
echo ""
echo "Then test with: docker ps"
