import React, { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useHotkeys } from 'react-hotkeys-hook';
import { useDrag } from '@use-gesture/react';
import * as Progress from '@radix-ui/react-progress';
import {
  Search,
  CheckCircle,
  XCircle,
  Edit3,
  Clock,
  Inbox,
  RefreshCw,
  AlertTriangle,
  Sparkles,
  MoreHorizontal,
  Zap,
  Undo2,
  X,
} from 'lucide-react';
import { supabase } from '../App';
import { useAuthContext } from '../hooks/useAuthContext';
import { useIsMobile } from '../hooks/use-mobile';
import { useScrollRestoration } from '../hooks/useScrollRestoration';
import { PillarBadge } from '../components/PillarBadge';
import { HorizonBadge } from '../components/HorizonBadge';
import { StageBadge } from '../components/StageBadge';
import { ConfidenceBadge } from '../components/ConfidenceBadge';
import { Tooltip } from '../components/ui/Tooltip';
import { cn } from '../lib/utils';
import { parseStageNumber } from '../lib/stage-utils';
import { VirtualizedList, VirtualizedListHandle } from '../components/VirtualizedList';
import {
  fetchPendingReviewCards,
  reviewCard,
  bulkReviewCards,
  dismissCard,
  type PendingCard,
  type ReviewAction,
  type DismissReason,
} from '../lib/discovery-api';

// DEBUG v7: Testing useIsMobile hook
const DiscoveryQueue: React.FC = () => {
  const { user } = useAuthContext();
  const isMobile = useIsMobile();

  if (!user) {
    return <div className="p-8">No user - redirecting...</div>;
  }

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold">Discovery Queue [v7-isMobile]</h1>
      <p className="mt-2">If you see this, useIsMobile works!</p>
      <p className="mt-1 text-gray-600">User: {user.email}</p>
      <p className="mt-1 text-gray-600">isMobile: {String(isMobile)}</p>
      <Link to="/" className="mt-4 inline-block text-blue-600 hover:underline">
        ← Back to Dashboard
      </Link>
    </div>
  );
};

export default DiscoveryQueue;
