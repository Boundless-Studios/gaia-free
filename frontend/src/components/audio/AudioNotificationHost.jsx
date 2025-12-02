import React, { useEffect, useRef, useState } from 'react';
import { Alert } from '../base-ui/Alert.jsx';
import './AudioNotificationHost.css';

const DEFAULT_DURATION = 6000;
const AUDIO_NOTIFICATION_EVENT = 'gaia:audio-notification';

const AudioNotificationHost = () => {
  const [items, setItems] = useState([]);
  const timeoutIdsRef = useRef(new Set());

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }

    let isMounted = true;

    const scheduleRemoval = (id, duration) => {
      const timeoutId = window.setTimeout(() => {
        if (!isMounted) {
          return;
        }
        setItems((previous) => previous.filter((item) => item.id !== id));
        timeoutIdsRef.current.delete(timeoutId);
      }, duration);

      timeoutIdsRef.current.add(timeoutId);
    };

    const handleNotification = (event) => {
      if (!isMounted) {
        return;
      }
      const detail = event.detail || {};
      if (!detail.message) {
        return;
      }

      const id = detail.id || `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
      const duration = typeof detail.duration === 'number' ? detail.duration : DEFAULT_DURATION;
      const variant = detail.variant === 'warning' ? 'warning' : 'error';

      setItems((previous) => [
        ...previous,
        {
          id,
          variant,
          message: detail.message,
        },
      ]);

      scheduleRemoval(id, duration);
    };

    window.addEventListener(AUDIO_NOTIFICATION_EVENT, handleNotification);

    return () => {
      isMounted = false;
      window.removeEventListener(AUDIO_NOTIFICATION_EVENT, handleNotification);
      timeoutIdsRef.current.forEach((timeoutId) => window.clearTimeout(timeoutId));
      timeoutIdsRef.current.clear();
    };
  }, []);

  if (!items.length) {
    return null;
  }

  const dismiss = (id) => {
    setItems((previous) => previous.filter((item) => item.id !== id));
  };

  return (
    <div className="audio-toast-host" data-testid="audio-toast-host">
      {items.map((item) => (
        <div key={item.id} className="audio-toast-host__item">
          <Alert
            variant={item.variant}
            onClose={() => dismiss(item.id)}
          >
            {item.message}
          </Alert>
        </div>
      ))}
    </div>
  );
};

export default AudioNotificationHost;
