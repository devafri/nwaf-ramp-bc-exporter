# Ramp → Business Central Export Tool

A user-friendly web application for exporting Ramp financial data to Business Central General Journal format.

## 🚀 Quick Start

### Option 1: Run Locally (for testing)

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up environment variables:**
   Create a `.env` file with your Ramp API credentials:
   ```
   RAMP_CLIENT_ID=your_client_id_here
   RAMP_CLIENT_SECRET=your_client_secret_here
   ```

3. **Run the app:**
   ```bash
   streamlit run streamlit_app.py
   ```

4. **Open your browser** to `http://localhost:8501`

### Option 2: Deploy to Streamlit Cloud (Recommended)

1. **Push to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/yourusername/ramp-bc-export.git
   git push -u origin main
   ```

2. **Deploy on Streamlit Cloud:**
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Connect your GitHub repository
   - Set main file path to `streamlit_app.py`
   - Add secrets in the Streamlit Cloud dashboard:
     ```
     RAMP_CLIENT_ID = "your_client_id_here"
     RAMP_CLIENT_SECRET = "your_client_secret_here"
     ```

3. **Share the URL** with your accountant!

### Option 3: Deploy to Other Platforms

#### Heroku:
```bash
# Create requirements.txt and runtime.txt
echo "python-3.9.13" > runtime.txt
heroku create your-app-name
git push heroku main
```

#### Railway:
- Connect your GitHub repo
- Add environment variables in Railway dashboard
- Deploy automatically

#### Vercel:
```bash
npm install -g vercel
vercel --prod
```

## 📋 Features

- ✅ **Web-based interface** - No CLI knowledge required
- ✅ **Date range selection** - Choose custom date ranges
- ✅ **Data type selection** - Export transactions, bills, reimbursements, etc.
- ✅ **Real-time progress** - See export progress and results
- ✅ **File downloads** - Download Excel and CSV files
- ✅ **Error handling** - Clear error messages and troubleshooting
- ✅ **Secure** - API credentials stored as environment variables

## 🔧 Configuration

### Required Files:
- `config.toml` - Business Central configuration
- `.env` - Ramp API credentials (local development)
- `streamlit_app.py` - Main application
- `ramp_client.py` - API client
- `transform.py` - Data transformation logic
- `bc_export.py` - Export utilities

### Environment Variables:
```
RAMP_CLIENT_ID=your_ramp_client_id
RAMP_CLIENT_SECRET=your_ramp_client_secret
```

## 🎯 User Guide

1. **Select Date Range:** Choose start and end dates for the export
2. **Choose Data Types:** Select which Ramp data to export (transactions, bills, reimbursements, etc.)
3. **Click "Run Export":** The app will fetch data and process it
4. **Download Files:** Download the Excel or CSV files for import into Business Central

## 🏢 Business Central Import

The exported files are formatted for Business Central General Journal import with:
- Proper G/L account coding
- Department and Activity codes
- Correct debit/credit accounting treatment
- All required journal fields

## 🆘 Troubleshooting

### Common Issues:

**"Authentication failed"**
- Check your Ramp API credentials in environment variables
- Ensure your OAuth app has the required scopes

**"No data found"**
- Verify the date range contains transactions
- Check that the selected data types are available

**"Error fetching [data_type]"**
- Some data types may not be available with your API permissions
- Check the app logs for detailed error messages

### Support:
- Check the Streamlit app logs for detailed error information
- Verify all required files are present
- Ensure Python dependencies are installed

## 🔒 Security Notes

- API credentials are stored securely as environment variables
- No sensitive data is logged or stored
- The app only reads data from Ramp (no write operations)
- Files are generated temporarily and downloaded directly

## 📝 License

This tool is provided as-is for Northwest Area Foundation use.