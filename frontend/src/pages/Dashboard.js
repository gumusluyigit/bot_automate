import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Grid,
  Paper,
  Typography,
  Button,
  CircularProgress,
} from '@mui/material';
import {
  CloudUpload as UploadIcon,
  List as ListIcon,
  Email as EmailIcon,
  Description as PDFIcon,
} from '@mui/icons-material';
import axios from 'axios';

const API_URL = 'http://localhost:5000';

function StatCard({ title, value, icon, color }) {
  return (
    <Paper
      sx={{
        p: 3,
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        bgcolor: `${color}.light`,
        color: `${color}.dark`,
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
        {icon}
        <Typography variant="h6" component="div" sx={{ ml: 1 }}>
          {title}
        </Typography>
      </Box>
      <Typography variant="h4" component="div">
        {value}
      </Typography>
    </Paper>
  );
}

function Dashboard() {
  const navigate = useNavigate();
  const [stats, setStats] = useState({
    pendingRequests: 0,
    processedPDFs: 0,
    sentEmails: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/pending_requests`);
      setStats({
        pendingRequests: response.data.length,
        processedPDFs: response.data.length, // This should be updated with actual stats
        sentEmails: response.data.filter(r => r.email_sent).length,
      });
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Box sx={{ flexGrow: 1, mt: 4 }}>
      <Typography variant="h4" gutterBottom>
        Dashboard
      </Typography>

      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid item xs={12} md={4}>
          <StatCard
            title="Pending Requests"
            value={stats.pendingRequests}
            icon={<ListIcon fontSize="large" />}
            color="primary"
          />
        </Grid>
        <Grid item xs={12} md={4}>
          <StatCard
            title="Processed PDFs"
            value={stats.processedPDFs}
            icon={<PDFIcon fontSize="large" />}
            color="success"
          />
        </Grid>
        <Grid item xs={12} md={4}>
          <StatCard
            title="Sent Emails"
            value={stats.sentEmails}
            icon={<EmailIcon fontSize="large" />}
            color="info"
          />
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              Quick Actions
            </Typography>
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
              <Button
                variant="contained"
                startIcon={<UploadIcon />}
                onClick={() => navigate('/upload')}
              >
                Upload New PDF
              </Button>
              <Button
                variant="outlined"
                startIcon={<ListIcon />}
                onClick={() => navigate('/pending')}
              >
                View Pending Requests
              </Button>
            </Box>
          </Paper>
        </Grid>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" gutterBottom>
              System Status
            </Typography>
            <Typography color="success.main" sx={{ display: 'flex', alignItems: 'center' }}>
              ● System is running normally
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              Last updated: {new Date().toLocaleString()}
            </Typography>
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}

export default Dashboard; 