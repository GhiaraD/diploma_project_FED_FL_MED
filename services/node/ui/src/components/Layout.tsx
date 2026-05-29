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
  IconButton,
  Menu,
  MenuItem,
  Divider,
  Avatar,
} from '@mui/material';
import {
  Dashboard as DashboardIcon,
  Folder as FolderIcon,
  Psychology as PsychologyIcon,
  School as SchoolIcon,
  Hub as HubIcon,
  Storage as StorageIcon,
  Work as WorkIcon,
  Security as SecurityIcon,
  AccountCircle,
  Logout as LogoutIcon,
} from '@mui/icons-material';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import { useApiInterceptor } from '@/hooks/useApiInterceptor';
import TokenExpirationWarning from './TokenExpirationWarning';
import { useState } from 'react';

const drawerWidth = 240;

const menuItems = [
  { text: 'Dashboard', icon: <DashboardIcon />, href: '/', requiredPermission: 'read:dashboard' },
  { text: 'Datasets', icon: <FolderIcon />, href: '/datasets', requiredPermission: 'read:datasets' },
  { text: 'Federated', icon: <HubIcon />, href: '/federated', requiredPermission: 'write:federated' },
  { text: 'Models', icon: <StorageIcon />, href: '/models', requiredPermission: 'read:models' },
  { text: 'Inference', icon: <PsychologyIcon />, href: '/inference', requiredPermission: 'read:inference' },
  { text: 'Jobs', icon: <WorkIcon />, href: '/jobs', requiredPermission: 'read:jobs' },
  { text: 'Audit', icon: <SecurityIcon />, href: '/audit', requiredPermission: 'admin' },
];

function hasPermission(role: string | undefined, required: string | null): boolean {
  if (required === null) return true;
  if (role === 'admin') return true;
  if (required === 'admin') return false;

  const permissionsMap: Record<string, string[]> = {
    doctor:     ['read:models', 'write:models', 'write:inference', 'read:inference', 'read:datasets', 'read:jobs', 'read:inference_history'],
    viewer:     ['read:models', 'read:inference', 'read:inference_history', 'read:jobs'],
  };

  return (permissionsMap[role ?? ''] ?? []).includes(required);
}

interface LayoutProps {
  children: ReactNode;
  title?: string;
  nodeId?: string;
}

export default function Layout({ children, title = 'Node Portal', nodeId }: LayoutProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();

  const resolvedNodeId = nodeId || user?.node_id;
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  // Use API interceptor for automatic token expiration handling
  useApiInterceptor();

  const handleMenu = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = async () => {
    handleClose();
    await logout();
    router.push('/login');
  };

  return (
    <Box sx={{ display: 'flex' }}>
      {/* Token Expiration Warning */}
      <TokenExpirationWarning />
      
      {/* AppBar */}
      <AppBar position="fixed" sx={{ zIndex: (theme) => theme.zIndex.drawer + 1 }}>
        <Toolbar>
          <Typography variant="h6" noWrap component="div" sx={{ flexGrow: 1 }}>
            Fed-Med-FL - {resolvedNodeId || title}
          </Typography>

          {/* User Menu */}
          {user && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <Box sx={{ textAlign: 'right', display: { xs: 'none', sm: 'block' } }}>
                <Typography variant="body2" sx={{ fontWeight: 500 }}>
                  {user.email}
                </Typography>
                <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>
                  {user.role.toUpperCase()} • {user.node_id.toUpperCase()}
                </Typography>
              </Box>
              <IconButton
                size="large"
                aria-label="account of current user"
                aria-controls="menu-appbar"
                aria-haspopup="true"
                onClick={handleMenu}
                color="inherit"
              >
                <Avatar sx={{ width: 32, height: 32, bgcolor: 'secondary.main' }}>
                  {user.email.charAt(0).toUpperCase()}
                </Avatar>
              </IconButton>
              <Menu
                id="menu-appbar"
                anchorEl={anchorEl}
                anchorOrigin={{
                  vertical: 'bottom',
                  horizontal: 'right',
                }}
                keepMounted
                transformOrigin={{
                  vertical: 'top',
                  horizontal: 'right',
                }}
                open={Boolean(anchorEl)}
                onClose={handleClose}
              >
                <MenuItem disabled>
                  <Box>
                    <Typography variant="body2" sx={{ fontWeight: 500 }}>
                      {user.email}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                      Role: {user.role}
                    </Typography>
                  </Box>
                </MenuItem>
                <Divider />
                <MenuItem onClick={handleLogout}>
                  <ListItemIcon>
                    <LogoutIcon fontSize="small" />
                  </ListItemIcon>
                  Logout
                </MenuItem>
              </Menu>
            </Box>
          )}
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
            {user && menuItems
              .filter((item) => {
                const result = hasPermission(user.role, item.requiredPermission);
                console.log(`[RBAC] role=${user.role} page=${item.text} required=${item.requiredPermission} → ${result}`);
                return result;
              })
              .map((item) => (
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
