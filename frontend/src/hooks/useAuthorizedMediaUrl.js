import { useEffect, useRef, useState } from 'react';
import apiService from '../services/apiService.js';

/**
 * Resolve a media URL requiring authentication by fetching it with authorized headers.
 * Returns a blob URL when needed so we avoid embedding JWTs in query strings.
 *
 * @param {string|null|undefined} rawUrl - The URL returned by the backend.
 * @returns {string|null} An absolute or blob URL safe to use in <img>/<audio> tags.
 */
const useAuthorizedMediaUrl = (rawUrl) => {
  const [resolvedUrl, setResolvedUrl] = useState(null);
  const [tokenVersion, setTokenVersion] = useState(apiService.tokenProviderVersion || 0);

  const objectUrlRef = useRef(null);

  useEffect(() => {
    const unsubscribe = apiService.subscribeTokenProvider((version) => {
      setTokenVersion(version);
    });
    return () => {
      unsubscribe();
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    const revokeObjectUrl = (url) => {
      if (
        !url ||
        typeof window === 'undefined' ||
        !window.URL ||
        typeof window.URL.revokeObjectURL !== 'function'
      ) {
        return;
      }
      try {
        window.URL.revokeObjectURL(url);
      } catch (error) {
        console.warn('Failed to revoke object URL:', error);
      }
    };

    const cleanupObjectUrl = () => {
      if (objectUrlRef.current) {
        revokeObjectUrl(objectUrlRef.current);
        objectUrlRef.current = null;
      }
    };

    async function resolve() {
      if (!rawUrl) {
        cleanupObjectUrl();
        if (!cancelled) {
          setResolvedUrl(null);
        }
        return;
      }

      try {
        const authorizedUrl = await apiService.buildAuthorizedMediaUrl(rawUrl);
        const isBlobUrl = typeof authorizedUrl === 'string' && authorizedUrl.startsWith('blob:');

        if (cancelled) {
          if (isBlobUrl) {
            revokeObjectUrl(authorizedUrl);
          }
          return;
        }

        if (isBlobUrl) {
          if (objectUrlRef.current && objectUrlRef.current !== authorizedUrl) {
            revokeObjectUrl(objectUrlRef.current);
          }
          objectUrlRef.current = authorizedUrl;
        } else {
          cleanupObjectUrl();
        }

        setResolvedUrl(authorizedUrl);
      } catch (error) {
        console.warn('Failed to authorize media URL:', error);
        cleanupObjectUrl();
        if (!cancelled) {
          setResolvedUrl(apiService.buildAbsoluteUrl(rawUrl));
        }
      }
    }

    resolve();

    return () => {
      cancelled = true;
      cleanupObjectUrl();
    };
  }, [rawUrl, tokenVersion]);

  return resolvedUrl;
};

export default useAuthorizedMediaUrl;
