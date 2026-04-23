'use client';
import { ReactNode } from 'react';
import {
  Box,
  AppBar,
  Toolbar,
  Typography,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Folder as FolderIcon,
  Psychology as PsychologyIcon,
  School as SchoolIcon,
  Hub as HubIcon,
  Storage as StorageIcon,
  Work as WorkIcon,
} from '@mui/icons-material';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

const drawerWidth = 240;

const menuItems = [
  { text: 'Dashboard', icon: <DashboardIcon />, href: '/' },
  { text: 'Studies', icon: <FolderIcon />, href: '/studies' },
  { text: 'Inference', icon: <PsychologyIcon />, href: '/inference' },
  { text: 'Train', icon: <SchoolIcon />, href: '/train' },
  { text: 'Federated', icon: <HubIcon />, href: '/federated' },
  { text: 'Models', icon: <StorageIcon />, href: '/models' },
  { text: 'Jobs', icon: <WorkIcon />, href: '/jobs' },
];

interface LayoutProps {
  children: ReactNode;
  title?: string;
  nodeId?: string;
}

export default function Layout({ children, title = 'Node Portal', nodeId }: LayoutProps) {
  const pathname = usePathname();

  return (
    <Box sx={{ display: 'flex' }}>
      {/* AppBar */}
      <AppBar position="fixed" sx={{ zIndex: (theme) => theme.zIndex.drawer + 1 }}>
        <Toolbar>
          <Typography variant="h6" noWrap component="div">
            Fed-Med-FL - {nodeId || title}
          </Typography>
        </Toolbar>
      </AppBar>

      {/* Drawer */}
      <Drawer
        variant="permanent"
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          [`& .MuiDrawer-paper`]: { width: drawerWidth, boxSizing: 'border-box' },
        }}
      >
        <Toolbar />
        <Box sx={{ overflow: 'auto' }}>
          <List>
            {menuItems.map((item) => (
              <ListItem key={item.text} disablePadding>
                <ListItemButton
                  component={Link}
                  href={item.href}
                  selected={pathname === item.href}
                >
                  <ListItemIcon>{item.icon}</ListItemIcon>
                  <ListItemText primary={item.text} />
                </ListItemButton>
              </ListItem>
            ))}
          </List>
        </Box>
      </Drawer>

      {/* Main Content */}
      <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
        <Toolbar />
        {children}
      </Box>
    </Box>
  );
}
