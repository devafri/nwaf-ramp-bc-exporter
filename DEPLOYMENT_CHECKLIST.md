# 🚀 Deployment Checklist: Ramp → Business Central Export Tool

## 📋 **Pre-Deployment Preparation**

### **1. Environment Setup**
- [ ] **Python Environment**: Ensure Python 3.8+ is available
- [ ] **Dependencies**: Verify all packages in `requirements.txt` are compatible
- [ ] **Local Testing**: Run `streamlit run streamlit_app.py` locally
- [ ] **Data Testing**: Test with sample data to ensure transformations work

### **2. Security Configuration**
- [ ] **API Credentials**: Obtain Ramp API client ID and secret
- [ ] **OAuth App**: Create/configure Ramp OAuth application with correct scopes
- [ ] **Streamlit Secrets**: Prepare secrets for Streamlit Cloud deployment
- [ ] **Access Control**: Determine who needs access to the deployed app

### **3. Code Review**
- [ ] **Error Handling**: Verify all error messages are sanitized
- [ ] **Credential Loading**: Confirm `st.secrets` usage (not environment variables)
- [ ] **Data Processing**: Ensure no sensitive data is logged or exposed
- [ ] **File Handling**: Confirm files are created in memory only

---

## 🌐 **Streamlit Cloud Deployment**

### **Step 1: Account Setup**
- [ ] Create Streamlit Cloud account (if not already done)
- [ ] Connect GitHub repository
- [ ] Verify repository access

### **Step 2: App Configuration**
- [ ] **Main File**: Set `streamlit_app.py` as main file path
- [ ] **Python Version**: Select Python 3.8 or higher
- [ ] **Requirements**: Ensure `requirements.txt` is in root directory

### **Step 3: Secrets Configuration**
Navigate to your app settings in Streamlit Cloud and add these secrets:

```
RAMP_CLIENT_ID = "your_ramp_client_id_here"
RAMP_CLIENT_SECRET = "your_ramp_client_secret_here"
```

**⚠️ Important**: Never commit secrets to your repository!

### **Step 4: Deploy**
- [ ] Click "Deploy" in Streamlit Cloud
- [ ] Monitor deployment logs for errors
- [ ] Verify the app loads successfully

---

## 🧪 **Post-Deployment Testing**

### **Functional Testing**
- [ ] **App Loads**: Verify the Streamlit app opens without errors
- [ ] **Authentication**: Test OAuth flow with Ramp
- [ ] **Data Fetching**: Test fetching different data types (transactions, bills, etc.)
- [ ] **Export Generation**: Test Excel/CSV export functionality
- [ ] **File Download**: Verify files download correctly

### **Security Testing**
- [ ] **No Credential Exposure**: Check that no API keys appear in UI
- [ ] **Error Messages**: Verify error messages don't reveal sensitive information
- [ ] **HTTPS**: Confirm the app uses HTTPS
- [ ] **Access Logs**: Review Streamlit Cloud access logs

### **Performance Testing**
- [ ] **Load Times**: Test with different data volumes
- [ ] **Memory Usage**: Monitor for memory issues with large datasets
- [ ] **API Limits**: Ensure respect for Ramp API rate limits

---

## 📤 **User Distribution**

### **Share with Accountant**
- [ ] **URL Sharing**: Provide the Streamlit Cloud URL
- [ ] **Usage Instructions**: Share `README_Streamlit.md`
- [ ] **Access Confirmation**: Verify they can access the app
- [ ] **Training**: Walk through the interface if needed

### **Documentation**
- [ ] **README Update**: Update with production URL
- [ ] **Security Docs**: Share `SECURITY.md` with IT/security team
- [ ] **Troubleshooting**: Prepare common issue resolution steps

---

## 🔍 **Monitoring & Maintenance**

### **Ongoing Monitoring**
- [ ] **Access Logs**: Regularly review Streamlit Cloud logs
- [ ] **Error Monitoring**: Set up alerts for application errors
- [ ] **API Usage**: Monitor Ramp API usage and limits
- [ ] **Performance**: Track app performance metrics

### **Maintenance Tasks**
- [ ] **Dependency Updates**: Keep packages updated for security
- [ ] **Code Updates**: Deploy bug fixes and improvements
- [ ] **Security Reviews**: Periodic security assessments
- [ ] **Backup Plans**: Document disaster recovery procedures

---

## 🚨 **Troubleshooting Common Issues**

### **Deployment Issues**
- **App won't start**: Check `requirements.txt` and Python version
- **Import errors**: Verify all dependencies are listed
- **Secrets not loading**: Ensure secrets are set in Streamlit Cloud settings

### **Runtime Issues**
- **Authentication fails**: Verify OAuth app configuration in Ramp
- **Data not loading**: Check API credentials and scopes
- **Export fails**: Test with smaller data sets first

### **Security Issues**
- **Credentials exposed**: Immediately rotate API keys and redeploy
- **Unauthorized access**: Review access logs and restrict sharing

---

## 📞 **Support Contacts**

- **Streamlit Cloud Support**: https://docs.streamlit.io/streamlit-cloud
- **Ramp API Support**: Check Ramp developer documentation
- **Your IT Team**: [contact information]

---

## ✅ **Final Verification**

Before marking deployment complete:

- [ ] App is accessible via public URL
- [ ] Authentication works correctly
- [ ] Data export functions properly
- [ ] No security vulnerabilities present
- [ ] Users can successfully use the application
- [ ] Monitoring is set up
- [ ] Documentation is current

---

**Deployment completed by:** [Your Name]  
**Date:** [Date]  
**Environment:** Streamlit Cloud  
**URL:** [Production URL]