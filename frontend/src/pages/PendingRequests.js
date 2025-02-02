import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Button,
  CircularProgress,
  Alert,
} from '@mui/material';
import {
  Email as EmailIcon,
  Download as DownloadIcon,
} from '@mui/icons-material';
import axios from 'axios';

const API_URL = 'http://localhost:5000';

function PendingRequests() {
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [emailStatus, setEmailStatus] = useState({});

  useEffect(() => {
    fetchPendingRequests();
  }, []);

  const fetchPendingRequests = async () => {
    try {
      const response = await axios.get(`${API_URL}/api/pending_requests`);
      setRequests(response.data);
      setError('');
    } catch (err) {
      setError('Failed to fetch pending requests');
    } finally {
      setLoading(false);
    }
  };

  const handleSendEmail = async (invoiceNumber, emailAddress) => {
    setEmailStatus(prev => ({ ...prev, [invoiceNumber]: 'sending' }));
    
    try {
      await axios.post(`${API_URL}/api/send_email`, {
        invoice_number: invoiceNumber,
        email_address: emailAddress,
      });
      
      setEmailStatus(prev => ({ ...prev, [invoiceNumber]: 'success' }));
      setTimeout(() => {
        setEmailStatus(prev => {
          const newStatus = { ...prev };
          delete newStatus[invoiceNumber];
          return newStatus;
        });
      }, 3000);
    } catch (err) {
      setEmailStatus(prev => ({ ...prev, [invoiceNumber]: 'error' }));
      setTimeout(() => {
        setEmailStatus(prev => {
          const newStatus = { ...prev };
          delete newStatus[invoiceNumber];
          return newStatus;
        });
      }, 3000);
    }
  };

  const handleDownloadPDF = async (invoiceNumber) => {
    try {
      const response = await axios.get(
        `${API_URL}/api/download_pdf/${invoiceNumber}`,
        { responseType: 'blob' }
      );
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${invoiceNumber}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      setError('Failed to download PDF');
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
    <Box sx={{ mt: 4 }}>
      <Typography variant="h4" gutterBottom>
        Pending Requests
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Invoice Number</TableCell>
              <TableCell>Company Name</TableCell>
              <TableCell>Period Start</TableCell>
              <TableCell>Period End</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {requests.map((request) => (
              <TableRow key={request.invoice_number}>
                <TableCell>{request.invoice_number}</TableCell>
                <TableCell>{request.company_name}</TableCell>
                <TableCell>{request.period_start}</TableCell>
                <TableCell>{request.period_end}</TableCell>
                <TableCell align="right">
                  <Box sx={{ display: 'flex', gap: 1, justifyContent: 'flex-end' }}>
                    <Button
                      variant="contained"
                      size="small"
                      startIcon={<EmailIcon />}
                      onClick={() => handleSendEmail(request.invoice_number, request.email)}
                      disabled={emailStatus[request.invoice_number] === 'sending'}
                    >
                      {emailStatus[request.invoice_number] === 'sending' ? (
                        <CircularProgress size={20} />
                      ) : 'Send Email'}
                    </Button>
                    <Button
                      variant="outlined"
                      size="small"
                      startIcon={<DownloadIcon />}
                      onClick={() => handleDownloadPDF(request.invoice_number)}
                    >
                      Download
                    </Button>
                  </Box>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}

export default PendingRequests; 