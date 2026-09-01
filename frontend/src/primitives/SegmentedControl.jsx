import React, { useId, useRef } from 'react';
import { motion } from 'framer-motion';

// SegmentedControl — a `radiogroup` of real, focusable buttons with a
// shared-layoutId sliding active indicator (the same mechanism the header
// nav's active-tab pill already uses, so the two read as one system rather
// than two different sliding-indicator implementations).
//
// Keyboard: ArrowLeft/ArrowRight/Home/End move both focus AND selection
// (standard tab/radiogroup behavior — a segmented control is a single
// choice, not a list of independent buttons), Enter/Space also select the
// focused option. Only the active segment is a tab-stop (roving tabindex),
// matching the WAI-ARIA radiogroup pattern.
export default function SegmentedControl({ options, value, onChange, label, className = '' }) {
  const groupId = useId();
  const refs = useRef({});

  const currentIndex = options.findIndex(o => o.value === value);

  const focusAndSelect = (index) => {
    const clamped = (index + options.length) % options.length;
    const opt = options[clamped];
    onChange(opt.value);
    refs.current[opt.value]?.focus();
  };

  const onKeyDown = (e) => {
    switch (e.key) {
      case 'ArrowRight':
      case 'ArrowDown':
        e.preventDefault();
        focusAndSelect(currentIndex + 1);
        break;
      case 'ArrowLeft':
      case 'ArrowUp':
        e.preventDefault();
        focusAndSelect(currentIndex - 1);
        break;
      case 'Home':
        e.preventDefault();
        focusAndSelect(0);
        break;
      case 'End':
        e.preventDefault();
        focusAndSelect(options.length - 1);
        break;
      default:
        break;
    }
  };

  return (
    <div
      className={`cc-segmented ${className}`}
      role="radiogroup"
      aria-label={label || 'Options'}
      onKeyDown={onKeyDown}
    >
      {options.map((opt) => {
        const isActive = opt.value === value;
        return (
          <button
            key={opt.value}
            ref={(el) => { refs.current[opt.value] = el; }}
            type="button"
            role="radio"
            aria-checked={isActive}
            tabIndex={isActive ? 0 : -1}
            className="cc-segmented-option"
            onClick={() => onChange(opt.value)}
            data-cursor="hover"
          >
            {isActive && (
              <motion.span
                layoutId={`cc-segmented-active-${groupId}`}
                className="cc-segmented-active"
                transition={{ type: 'spring', stiffness: 500, damping: 36 }}
              />
            )}
            <span className="cc-segmented-label">{opt.label}</span>
          </button>
        );
      })}
    </div>
  );
}
