import { useId } from "react";

interface BrandLogoProps {
  className?: string;
}

export function BrandLogo({ className = "size-10" }: BrandLogoProps) {
  const uid = useId().replace(/:/g, "");
  const bgId = `ms-bg-${uid}`;
  const rimId = `ms-rim-${uid}`;
  const limeId = `ms-lime-${uid}`;

  return (
    <svg
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role="img"
      aria-label="MetaStudio logo"
    >
      <defs>
        <linearGradient id={bgId} x1="8" y1="4" x2="56" y2="60" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#1d2433" />
          <stop offset="100%" stopColor="#0d111a" />
        </linearGradient>
        <linearGradient id={rimId} x1="8" y1="4" x2="56" y2="60" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#c8fa4e" stopOpacity="0.6" />
          <stop offset="50%" stopColor="#ffffff" stopOpacity="0.14" />
          <stop offset="100%" stopColor="#60b6f5" stopOpacity="0.28" />
        </linearGradient>
        <linearGradient id={limeId} x1="16" y1="14" x2="48" y2="50" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#dcff66" />
          <stop offset="100%" stopColor="#98e62e" />
        </linearGradient>
      </defs>

      <rect
        x="2"
        y="2"
        width="60"
        height="60"
        rx="15"
        fill={`url(#${bgId})`}
        stroke={`url(#${rimId})`}
        strokeWidth="2"
      />
      <circle cx="32" cy="32" r="22" stroke="#c8fa4e" strokeOpacity="0.14" strokeWidth="1.5" />

      <rect x="14.5" y="18" width="5.5" height="28" rx="2.75" fill={`url(#${limeId})`} />
      <rect
        x="22"
        y="21.5"
        width="5.5"
        height="19"
        rx="2.75"
        fill={`url(#${limeId})`}
        fillOpacity="0.92"
      />
      <rect x="29.25" y="28" width="5.5" height="15" rx="2.75" fill={`url(#${limeId})`} />
      <rect
        x="36.5"
        y="21.5"
        width="5.5"
        height="19"
        rx="2.75"
        fill={`url(#${limeId})`}
        fillOpacity="0.92"
      />
      <rect x="44" y="18" width="5.5" height="28" rx="2.75" fill={`url(#${limeId})`} />

      <circle cx="49.5" cy="13.5" r="2.75" fill="#60b6f5" />
      <circle cx="14.5" cy="50.5" r="2.25" fill="#f0ad5e" />
    </svg>
  );
}
