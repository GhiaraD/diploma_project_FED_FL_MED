# Dataset UI Update - Green Background Removed

## Changes Made

### Visual Update
Removed the green background (`bgcolor: 'success.light'`) from the Active Dataset card in the Datasets page.

**Before:**
```tsx
<Paper sx={{ p: 3, mb: 3, bgcolor: 'success.light' }}>
```

**After:**
```tsx
<Paper sx={{ p: 3, mb: 3 }}>
```

The card now uses the default white background like the rest of the UI, maintaining a clean and consistent look.

### Active Dataset Card Features
The card still displays:
- ✅ Green checkmark icon to indicate active status
- ✅ Dataset name (bold)
- ✅ Split type
- ✅ Total samples count
- ✅ 3-column horizontal layout

## Containers Updated

All three node UI containers have been rebuilt and restarted with the changes:

1. **Node1 UI** (port 3001)
   - Image: `diploma_project_fed_fl_med-node1-ui`
   - Status: ✅ Running

2. **Node2 UI** (port 3002)
   - Image: `diploma_project_fed_fl_med-node2-ui`
   - Status: ✅ Running

3. **Node3 UI** (port 3003)
   - Image: `diploma_project_fed_fl_med-node3-ui`
   - Status: ✅ Running

## Build Commands Used

```bash
# Rebuild UI images
docker build -t diploma_project_fed_fl_med-node1-ui -f ./services/node/ui/Dockerfile ./services/node/ui
docker build -t diploma_project_fed_fl_med-node2-ui -f ./services/node/ui/Dockerfile ./services/node/ui
docker build -t diploma_project_fed_fl_med-node3-ui -f ./services/node/ui/Dockerfile ./services/node/ui

# Restart containers
docker restart diploma_project_fed_fl_med-node1-ui-1
docker restart diploma_project_fed_fl_med-node2-ui-1
docker restart diploma_project_fed_fl_med-node3-ui-1
```

## Files Modified
- `services/node/ui/src/app/datasets/page.tsx` - Removed green background from Active Dataset card

## Access URLs
- Node1: http://localhost:3001/datasets
- Node2: http://localhost:3002/datasets
- Node3: http://localhost:3003/datasets

## Status
✅ **COMPLETE** - All three nodes now display the Active Dataset card with white background.
