/**
 * CreateSignal Module
 *
 * Barrel export for the Create Signal modal and its sub-components.
 *
 * @example
 * ```tsx
 * import { CreateSignalModal } from '../components/CreateSignal';
 *
 * function MyPage() {
 *   const [open, setOpen] = useState(false);
 *   return <CreateSignalModal isOpen={open} onClose={() => setOpen(false)} />;
 * }
 * ```
 *
 * @module CreateSignal
 */

export { CreateSignalModal } from "./CreateSignalModal";
export type { CreateSignalModalProps } from "./CreateSignalModal";

export { QuickCreateTab } from "./QuickCreateTab";
export type { QuickCreateTabProps } from "./QuickCreateTab";

export { ManualCreateTab } from "./ManualCreateTab";
export type { ManualCreateTabProps } from "./ManualCreateTab";

export { SeedUrlInput } from "./SeedUrlInput";
export type { SeedUrlInputProps } from "./SeedUrlInput";

export { SourcePreferencesStep } from "./SourcePreferencesStep";
export type {
  SourcePreferences,
  SourcePreferencesStepProps,
} from "./SourcePreferencesStep";
