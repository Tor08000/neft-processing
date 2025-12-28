import React from "react";

interface RiskProfilePickerProps {
  profiles: { id: string; name?: string | null }[];
  value?: string;
  onChange: (value: string) => void;
}

export const RiskProfilePicker: React.FC<RiskProfilePickerProps> = ({ profiles, value, onChange }) => {
  return (
    <label>
      Risk profile
      <select value={value ?? ""} onChange={(event) => onChange(event.target.value)}>
        <option value="">Не выбрано</option>
        {profiles.map((profile) => (
          <option key={profile.id} value={profile.id}>
            {profile.name ?? profile.id}
          </option>
        ))}
      </select>
    </label>
  );
};
