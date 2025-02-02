import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { Container } from '@mui/material';

// Import pages
import Dashboard from './pages/Dashboard';
import PDFUpload from './pages/PDFUpload';
import PendingRequests from './pages/PendingRequests';

// Import components
import Navigation from './components/Navigation';

// Create a theme
const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
    },
  },
});

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Router>
        <Navigation />
        <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/upload" element={<PDFUpload />} />
            <Route path="/pending" element={<PendingRequests />} />
          </Routes>
        </Container>
      </Router>
    </ThemeProvider>
  );
}

export default App; 