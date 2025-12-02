import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { API_CONFIG } from '../config/api.js';
import apiService from '../services/apiService.js';
import { Button } from './base-ui/Button';
import { Input } from './base-ui/Input';
import { Select } from './base-ui/Select';
import { useLoading, LoadingTypes } from '../contexts/LoadingContext';
import './ImageGenerateButton.css';

const ImageGenerateButton = forwardRef(({ onImageGenerated, campaignId }, ref) => {
    const { setLoading } = useLoading();
    const [isGenerating, setIsGenerating] = useState(false);
    const [hasSelection, setHasSelection] = useState(false);
    const [queueSize, setQueueSize] = useState(0);
    const queueRef = useRef([]);
    const processingRef = useRef(false);
    const [clickAnimation, setClickAnimation] = useState(false);
    const [imageType, setImageType] = useState('scene');
    const [customType, setCustomType] = useState('');
    const [showCustomInput, setShowCustomInput] = useState(false);
    const [queuedTypes, setQueuedTypes] = useState([]);
    
    // Model selection state - following TTS pattern
    const [models, setModels] = useState([]);
    const [selectedModel, setSelectedModel] = useState(null);
    const [isLoadingModels, setIsLoadingModels] = useState(true);

    useEffect(() => {
        // Add selection change listener
        const handleSelectionChange = () => {
            const selection = window.getSelection();
            const hasText = selection && selection.toString().trim().length > 0;
            setHasSelection(hasText);
        };

        document.addEventListener('selectionchange', handleSelectionChange);
        
        // Check initial selection
        handleSelectionChange();

        return () => {
            document.removeEventListener('selectionchange', handleSelectionChange);
        };
    }, []);

    // Load available models - following TTS pattern
    useEffect(() => {
        fetchAvailableModels();
    }, []);

    const fetchAvailableModels = async () => {
        try {
            setIsLoadingModels(true);
            setLoading(LoadingTypes.MODEL_LOADING, true);
            console.log('Fetching image models from:', `${API_CONFIG.BACKEND_URL}/api/image-models`);
            
            const data = await apiService.getImageModels();
            console.log('Image models response:', data);
            
            if (data.models && Array.isArray(data.models)) {
                setModels(data.models);
                setSelectedModel(data.current_model);
                console.log(`Loaded ${data.models.length} models, current: ${data.current_model}`);
            } else {
                console.error('Invalid response format - models is not an array:', data);
                setModels([]);
                setSelectedModel(null);
            }
        } catch (err) {
            console.error('Failed to load image models:', err);
            setModels([]);
            setSelectedModel(null);
        } finally {
            setIsLoadingModels(false);
            setLoading(LoadingTypes.MODEL_LOADING, false);
        }
    };

    const handleModelChange = async (modelKey) => {
        try {
            const data = await apiService.switchImageModel({ model_key: modelKey });
            
            if (data) {
                setSelectedModel(modelKey);
                console.log(`Switched to image model: ${data.model.name}`);
            }
        } catch (err) {
            console.error('Failed to switch image model:', err);
        }
    };

    const processNextInQueue = async () => {
        console.log('[ImageGen] processNextInQueue called, queue length:', queueRef.current.length, 'processing:', processingRef.current);
        
        if (queueRef.current.length === 0 || processingRef.current) {
            console.log('[ImageGen] Skipping - empty queue or already processing');
            return;
        }

        processingRef.current = true;
        setIsGenerating(true);

        const nextItem = queueRef.current.shift();
        const remainingQueueSize = queueRef.current.length;
        setQueueSize(remainingQueueSize);
        // Update queued types display
        setQueuedTypes(queueRef.current.map(item => item.type));
        // Update global loading context with queue count
        setLoading(LoadingTypes.IMAGE_GENERATION, true, remainingQueueSize);
        console.log('[ImageGen] Processing prompt:', nextItem.prompt, 'Type:', nextItem.type, 'Model:', selectedModel, 'Remaining in queue:', queueRef.current.length);
        
        try {
            console.log('Generating image for:', nextItem.prompt, 'Type:', nextItem.type, 'Model:', selectedModel);
            
            const requestBody = {
                prompt: nextItem.prompt,
                image_type: nextItem.type,
                campaign_id: campaignId || 'default'
            };
            
            // Add model parameter if a model is selected
            if (selectedModel) {
                requestBody.model = selectedModel;
            }
            
            // Add timeout to prevent hanging requests (120 seconds for image generation)
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 120000);
            
            // Use apiService which handles Auth0 token automatically
            const data = await apiService.generateImage(requestBody);
            
            clearTimeout(timeoutId);
            
            if (data) {
                console.log('Image generation response:', data);
                
                if (data.success && data.image) {
                    // Format the image data to match the expected structure
                    const imageData = {
                        generated_image_url: data.image.image_url || data.image.url,
                        generated_image_path: data.image.local_path || data.image.path,
                        generated_image_prompt: data.image.prompt || data.image.original_prompt || nextItem.prompt,
                        generated_image_type: nextItem.type
                    };
                    console.log('ImageGenerateButton - formatted imageData:', imageData);
                    if (onImageGenerated) {
                        onImageGenerated(imageData);
                    }
                }
            }
        } catch (error) {
            console.error('Failed to generate image:', error);
        }
        
        processingRef.current = false;
        
        // Check if there are more items in queue
        console.log('[ImageGen] Finished processing, queue length:', queueRef.current.length);
        if (queueRef.current.length > 0) {
            console.log('[ImageGen] More items in queue, scheduling next processing');
            setTimeout(processNextInQueue, 100);
        } else {
            console.log('[ImageGen] Queue empty, stopping');
            setIsGenerating(false);
            setLoading(LoadingTypes.IMAGE_GENERATION, false, 0);
            setQueuedTypes([]);
        }
    };

    const handleGenerateImage = () => {
        const selection = window.getSelection();
        const selectedText = selection ? selection.toString().trim() : '';

        if (!selectedText) {
            console.log('[ImageGen] No text selected, skipping');
            return;
        }
        
        // Check if this text is already being processed or in queue
        if (processingRef.current && queueRef.current.length === 0) {
            // If we're processing and queue is empty, the current item might be the same
            console.log('[ImageGen] Already processing, adding to queue');
        }
        
        // Trigger click animation
        setClickAnimation(true);
        setTimeout(() => setClickAnimation(false), 200);

        // Capture the current type at queue time (support custom input)
        const finalType = showCustomInput
            ? (customType.trim() || 'scene')
            : ((imageType || '').trim() || 'scene');
        const queueItem = {
            prompt: selectedText,
            type: finalType,
            queuedAt: new Date().toISOString()
        };
        
        queueRef.current.push(queueItem);
        const currentQueueSize = queueRef.current.length;
        setQueueSize(currentQueueSize);
        // Update queued types display
        setQueuedTypes(queueRef.current.map(item => item.type));
        console.log('[ImageGen] Added to queue:', selectedText, 'Type:', finalType, 'Queue size:', currentQueueSize);

        // Update global loading context immediately with new queue size
        if (processingRef.current) {
            // If already processing, show the queue count (minus 1 for the item being processed)
            setLoading(LoadingTypes.IMAGE_GENERATION, true, currentQueueSize - 1);
        }

        // Start processing if not already
        if (!processingRef.current) {
            console.log('[ImageGen] Starting processing');
            processNextInQueue();
        } else {
            console.log('[ImageGen] Already processing, item queued with type:', finalType);
        }
    };
    
    // Expose method for external triggering (keyboard shortcut)
    useImperativeHandle(ref, () => ({
        generateFromSelection: () => {
            handleGenerateImage();
        },
        generateFromSelectionWithType: (newImageType) => {
            // Generate with the specified type directly, without changing state
            const selection = window.getSelection();
            const selectedText = selection ? selection.toString().trim() : '';
            
            if (!selectedText) {
                console.log('[ImageGen] No text selected for keyboard shortcut');
                return;
            }
            
            // Check if this text is already being processed or in queue
            if (processingRef.current && queueRef.current.length === 0) {
                // If we're processing and queue is empty, the current item might be the same
                console.log('[ImageGen] Already processing, adding to queue');
            }
            
            // Trigger click animation
            setClickAnimation(true);
            setTimeout(() => setClickAnimation(false), 200);
            
            // Create queue item with the specified type
            const queueItem = {
                prompt: selectedText,
                type: newImageType,
                queuedAt: new Date().toISOString()
            };
            
            queueRef.current.push(queueItem);
            const currentQueueSize = queueRef.current.length;
            setQueueSize(currentQueueSize);
            setQueuedTypes(queueRef.current.map(item => item.type));
            console.log('[ImageGen] Added to queue via keyboard shortcut:', selectedText, 'Type:', newImageType, 'Queue size:', currentQueueSize);

            // Update global loading context immediately with new queue size
            if (processingRef.current) {
                // If already processing, show the queue count (minus 1 for the item being processed)
                setLoading(LoadingTypes.IMAGE_GENERATION, true, currentQueueSize - 1);
            }

            // Start processing if not already
            if (!processingRef.current) {
                processNextInQueue();
            }
        }
    }));

    return (
        <div className="image-generate-container">
            {/* Model Selector */}
            {isLoadingModels ? (
                <div className="model-selector-loading">
                    <span>Loading models...</span>
                </div>
            ) : (
                <Select
                    className="image-type-dropdown"
                    value={selectedModel || ''}
                    onChange={handleModelChange}
                    disabled={models.length === 0}
                    isInPopup={true}
                    forceNative={true}
                    options={models.length === 0 ? 
                        [{ value: '', label: 'No models available' }] :
                        models.map(model => ({
                            value: model.key,
                            label: `${model.name} (${model.steps} steps)`
                        }))
                    }
                />
            )}

            {/* Image Type Select with Custom option */}
            <Select 
                className="image-type-dropdown"
                value={imageType}
                onChange={(value) => {
                    setImageType(value);
                    setShowCustomInput(value === 'custom');
                }}
                disabled={false}
                isInPopup={true}
                forceNative={true}
                options={[  
                    { value: 'scene', label: 'Scene' },
                    { value: 'character', label: 'Character' },
                    { value: 'portrait', label: 'Portrait' },
                    { value: 'item', label: 'Item' },
                    { value: 'beast', label: 'Beast' },
                    { value: 'moment', label: 'Moment' },
                    { value: 'custom', label: 'Custom...' },
                ]}
            />
            {showCustomInput && (
                <Input
                    type="text"
                    className="custom-type-input"
                    placeholder="Enter custom type..."
                    value={customType}
                    onChange={(e) => setCustomType(e.target.value)}
                    disabled={false}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter' && hasSelection) {
                            handleGenerateImage();
                        }
                    }}
                />
            )}
            <Button 
                className={`image-generate-button ${isGenerating ? 'loading' : ''} ${hasSelection ? 'has-selection' : ''} ${clickAnimation ? 'clicked' : ''}`}
                onClick={handleGenerateImage}
                disabled={!hasSelection}
                title={hasSelection ? (isGenerating ? (queueSize > 0 ? `Generating image • ${queueSize} queued` : 'Generating image...') : "Generate image from selected text") : "Select text in narrative, then click to generate image"}
                loading={isGenerating}
                loadingCount={queueSize}
            >
                {isGenerating ? (
                    <span className="flex flex-col items-start leading-tight">
                        <span>Generating...</span>
                        {queuedTypes.length > 0 && (
                            <span className="text-xs text-gaia-text-dim">
                                Next: {queuedTypes[0]}
                            </span>
                        )}
                    </span>
                ) : (
                    <>
                        <span className="generate-icon">🎨</span>
                        <span>Generate Image</span>
                    </>
                )}
                {hasSelection && <span className="selection-indicator">●</span>}
            </Button>
        </div>
    );
});

ImageGenerateButton.displayName = 'ImageGenerateButton';

export default ImageGenerateButton;
