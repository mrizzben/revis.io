import { useState, useEffect, type FormEvent } from 'react';
import Modal from '../ui/Modal';
import Input from '../ui/Input';
import TextArea from '../ui/TextArea';
import Button from '../ui/Button';

interface MilestoneFormData {
  name: string;
  description?: string;
  position?: number;
}

interface MilestoneFormProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: MilestoneFormData) => Promise<void>;
  initialData?: MilestoneFormData;
  isLoading?: boolean;
}

export default function MilestoneForm({
  isOpen,
  onClose,
  onSubmit,
  initialData,
  isLoading = false,
}: MilestoneFormProps) {
  const isEdit = !!initialData;

  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [position, setPosition] = useState<string>('');
  const [errors, setErrors] = useState<{ name?: string }>({});

  const title = isEdit ? 'Edit Milestone' : 'New Milestone';

  useEffect(() => {
    if (isOpen) {
      setName(initialData?.name ?? '');
      setDescription(initialData?.description ?? '');
      setPosition(initialData?.position != null ? String(initialData.position) : '');
      setErrors({});
    }
  }, [isOpen, initialData]);

  function validate(): boolean {
    const next: { name?: string } = {};
    const trimmed = name.trim();

    if (!trimmed) {
      next.name = 'Name is required';
    } else if (trimmed.length > 255) {
      next.name = 'Name must be 255 characters or fewer';
    }

    setErrors(next);
    return Object.keys(next).length === 0;
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!validate()) return;

    const data: MilestoneFormData = { name: name.trim() };
    if (description.trim()) data.description = description.trim();
    if (position !== '') {
      const num = parseInt(position, 10);
      if (!isNaN(num)) data.position = num;
    }

    await onSubmit(data);
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title} size="sm">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Name"
          value={name}
          onChange={(e) => setName((e.target as HTMLInputElement).value)}
          error={errors.name}
          placeholder="e.g. Schematic Design Review"
          maxLength={255}
          required
          autoFocus
        />

        <TextArea
          label="Description"
          value={description}
          onChange={(e) => setDescription((e.target as HTMLTextAreaElement).value)}
          placeholder="Optional description of this milestone"
          rows={3}
        />

        <Input
          label="Position"
          type="number"
          value={position}
          onChange={(e) => setPosition((e.target as HTMLInputElement).value)}
          placeholder="Optional ordering number"
          hint="Lower numbers appear first. Leave blank for auto-assignment."
          min={0}
        />

        <div className="flex items-center justify-end gap-3 pt-2">
          <Button type="button" variant="secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button type="submit" isLoading={isLoading} disabled={isLoading}>
            {isEdit ? 'Save Changes' : 'Create Milestone'}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
