#!/bin/bash
# Deploy to Streamlit Cloud
echo "🚀 Deploying to Streamlit Cloud..."

# Check if git repo exists
if [ ! -d ".git" ]; then
    echo "📝 Initializing git repository..."
    git init
    git add .
    git commit -m "Initial Ramp BC Export app"
fi

echo "📤 Pushing to GitHub..."
echo "Make sure to:"
echo "1. Create a GitHub repository"
echo "2. Update the git remote URL below"
echo "3. Push to GitHub"
echo ""
echo "Commands to run:"
echo "git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git"
echo "git branch -M main"
echo "git push -u origin main"
echo ""
echo "Then visit: https://share.streamlit.io"
echo "1. Connect your GitHub repo"
echo "2. Set main file: streamlit_app.py"
echo "3. Add secrets: RAMP_CLIENT_ID and RAMP_CLIENT_SECRET"