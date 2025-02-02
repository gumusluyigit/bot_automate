import React from 'react';
import { Link as RouterLink } from 'react-router-dom';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
} from '@mui/material';
import {
  CloudUpload as UploadIcon,
  List as ListIcon,
  Dashboard as DashboardIcon,
} from '@mui/icons-material';

function Navigation() {
  return (
    <AppBar position="static">
      <Toolbar>
        <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
          Receipt Automation
        </Typography>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            color="inherit"
            component={RouterLink}
            to="/"
            startIcon={<DashboardIcon />}
          >
            Dashboard
          </Button>
          <Button
            color="inherit"
            component={RouterLink}
            to="/upload"
            startIcon={<UploadIcon />}
          >
            Upload PDF
          </Button>
          <Button
            color="inherit"
            component={RouterLink}
            to="/pending"
            startIcon={<ListIcon />}
          >
            Pending Requests
          </Button>
        </Box>
      </Toolbar>
    </AppBar>
  );
}

export default Navigation; 