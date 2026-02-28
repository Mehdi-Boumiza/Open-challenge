const translations = {
    fr: {
        title: "Détection des Maladies du Blé",
        fileLabel: "Sélectionner des images",
        noFile: "Aucun fichier sélectionné",
        filesSelected: "fichier(s) sélectionné(s)",
        langLabel: "Langue:",
        analyzeBtn: "Analyser",
        loading: "Analyse en cours...",
        filename: "Fichier:",
        disease: "Maladie:",
        severity: "Sévérité:",
        tips: "Recommandations:",
        error: "Erreur lors de l'analyse. Veuillez réessayer.",
        noImages: "Veuillez sélectionner au moins une image."
    },
    ar: {
        title: "كشف أمراض القمح",
        fileLabel: "اختر الصور",
        noFile: "لم يتم اختيار أي ملف",
        filesSelected: "ملف(ات) محددة",
        langLabel: "اللغة:",
        analyzeBtn: "تحليل",
        loading: "جاري التحليل...",
        filename: "الملف:",
        disease: "المرض:",
        severity: "الشدة:",
        tips: "التوصيات:",
        error: "حدث خطأ أثناء التحليل. يرجى المحاولة مرة أخرى.",
        noImages: "يرجى تحديد صورة واحدة على الأقل."
    }
};

const staticText = {
    fr: {
        photoHint: " Prenez une photo des feuilles de blé uniquement (pas des racines ni des épis), puis cliquez sur « Analyser »",
        leafWarning: " Cette application fonctionne uniquement sur les feuilles de blé. Les photos floues ou d’autres parties peuvent donner des résultats inexacts.",
        resultsTitle: "Résultat du diagnostic",
        resultsNote: "Les résultats sont indicatifs et ne remplacent pas l’avis d’un ingénieur agronome en cas grave."
    },
    ar: {
        photoHint: " التقط صورة لأوراق القمح فقط (ليس الجذور أو السنابل)، ثم اضغط على « تحليل »",
        leafWarning: " هذا التطبيق يعمل فقط على أوراق القمح. الصور غير الواضحة أو لأجزاء أخرى قد تعطي نتائج غير دقيقة.",
        resultsTitle: "نتيجة التشخيص",
        resultsNote: "النتائج تقديرية ولا تُغني عن استشارة مهندس فلاحي في الحالات الخطيرة"
    }
};


// DOM Elements
const imageInput = document.getElementById('imageInput');
const languageSelect = document.getElementById('languageSelect');
const analyzeBtn = document.getElementById('analyzeBtn');
const loadingIndicator = document.getElementById('loadingIndicator');
const resultsContainer = document.getElementById('resultsContainer');
const fileCount = document.getElementById('fileCount');

// Update UI text based on selected language
function updateLanguage() {
    const lang = languageSelect.value;
    const t = translations[lang];
    
    document.getElementById('mainTitle').textContent = t.title;
    document.getElementById('fileLabel').textContent = t.fileLabel;
    document.getElementById('langLabel').textContent = t.langLabel;
    analyzeBtn.textContent = t.analyzeBtn;
    document.getElementById('loadingText').textContent = t.loading;
    
    // Apply RTL for Arabic
    if (lang === 'ar') {
        document.body.classList.add('rtl');
    } else {
        document.body.classList.remove('rtl');
    }
    
    // Update file count text
    updateFileCount();
    updateStaticText(lang);
}

function previewImages() {
    const previewContainer = document.getElementById('previewContainer');
    previewContainer.innerHTML = ''; // Clear previous previews
    
    const files = imageInput.files;
    
    if (files) {
        Array.from(files).forEach(file => {
            const reader = new FileReader();
            
            reader.onload = function(e) {
                const img = document.createElement('img');
                img.src = e.target.result;
                img.classList.add('thumbnail');
                previewContainer.appendChild(img);
            }
            
            reader.readAsDataURL(file);
        });
    }
}


function updateStaticText(lang) {
    const s = staticText[lang];

    const photoHint = document.getElementById("photoHint");
    const leafWarning = document.getElementById("leafWarning");
    const resultsTitle = document.getElementById("resultsTitle");
    const resultsNote = document.getElementById("resultsNote");

    if (photoHint) photoHint.textContent = s.photoHint;
    if (leafWarning) leafWarning.textContent = s.leafWarning;
    if (resultsTitle) resultsTitle.textContent = s.resultsTitle;
    if (resultsNote) resultsNote.textContent = s.resultsNote;

    document.body.classList.toggle("rtl", lang === "ar");
}

// Update file count display
function updateFileCount() {
    const lang = languageSelect.value;
    const t = translations[lang];
    const files = imageInput.files;
    
    if (files.length === 0) {
        fileCount.textContent = t.noFile;
    } else {
        fileCount.textContent = `${files.length} ${t.filesSelected}`;
    }
}

imageInput.addEventListener('change', () => {
    updateFileCount();
    previewImages(); // Call the new preview function
});

// Event Listeners
languageSelect.addEventListener('change', updateLanguage);

// Analyze button click handler
analyzeBtn.addEventListener('click', async () => {
    const files = imageInput.files;
    const lang = languageSelect.value;
    const t = translations[lang];
    
    // Validate file selection
    if (files.length === 0) {
        alert(t.noImages);
        return;
    }
    
    // Only allow single image
    if (files.length > 1) {
        alert(lang === 'fr' 
            ? 'Veuillez sélectionner une seule image à la fois.'
            : 'يرجى تحديد صورة واحدة فقط في كل مرة.');
        return;
    }
    
    // Show loading indicator
    loadingIndicator.classList.remove('hidden');
    resultsContainer.innerHTML = '';
    analyzeBtn.disabled = true;
    
    try {
        // Prepare FormData with SINGLE image
        const formData = new FormData();
        formData.append('file', files[0]);
        
        // Send request to backend
        const response = await fetch('/api/analyze', {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        // Parse JSON response
        const result = await response.json();
        
        // Display result
        displayResults([result], lang);
        
    } catch (error) {
        console.error('Error during analysis:', error);
        alert(t.error);
    } finally {
        // Hide loading indicator and re-enable button
        loadingIndicator.classList.add('hidden');
        analyzeBtn.disabled = false;
    }
});

function isNonDiseaseLabel(label) {
    if (!label) return false;
    const l = label.toLowerCase();
    return (
        l.includes("brûlure") ||
        l.includes("brulure") ||
        l.includes("burn")
    );
}

// Display results in cards
function displayResults(results, lang) {
    const t = translations[lang];
    resultsContainer.innerHTML = '';
    
    results.forEach(result => {
        // Create result card
        const card = document.createElement('div');
        card.className = 'result-card certain'; // Always show as certain
        
        let rawDiseaseLabel = null;

        if (lang === 'fr') {
            rawDiseaseLabel =
                result.disease_fr ||
                result.disease ||
                result.label ||
                result.class_name ||
                null;
        } else {
            rawDiseaseLabel =
                result.disease_ar ||
                result.disease ||
                result.label ||
                result.class_name ||
                null;
        }

        const severityLevel = result.severity || 'unknown';
        let severityLabel = '';
        let severityClass = '';
        let severityIcon = '';

        if (severityLevel === 'high') {
            severityIcon = '';
            severityLabel = lang === 'fr' ? 'DANGER  Sévérité élevée' : 'خطر – شدة مرتفعة';
            severityClass = 'severity-high';
        } else if (severityLevel === 'medium') {
            severityIcon = '';
            severityLabel = lang === 'fr' ? 'Attention  Sévérité moyenne' : 'تنبيه – شدة متوسطة';
            severityClass = 'severity-medium';
        } else if (severityLevel === 'low') {
            severityIcon = '';
            severityLabel = lang === 'fr' ? 'Faible sévérité' : 'شدة منخفضة';
            severityClass = 'severity-low';
        }
        
        // Build card content
        let cardHTML = `
            <h3>${result.filename || 'Diagnostic'}</h3>
            
            <div class="info-row">
                <span class="label">${t.disease}</span>
                <span class="value disease">
                    ${rawDiseaseLabel || 'Rouille jaune(لصدأ الأصفر)'}
                </span>
            </div>
            
            ${severityLabel ? `
            <div class="severity-banner ${severityClass}">
                ${severityIcon} ${severityLabel}
            </div>` : ''}
            
        `;
        
        // Determine tips/recommendations based on language
        let tipsContent = '';
        if (lang === 'fr') {
            tipsContent = result.tip_fr || result.recommendation_fr || '';
        } else if (lang === 'ar') {
            tipsContent = result.tip_ar || result.recommendation_ar || '';
        } else {
            tipsContent = result.tips || result.recommendations || '';
        }
        
        // Add tips/recommendations
        let finalTips = '';
        if (severityLevel === 'high') {
            finalTips = lang === 'fr'
                ? 'Appliquez rapidement un traitement adapté et consultez un ingénieur agronome.'
                : 'ابدأ العلاج فورًا واستشر مهندسًا فلاحيًا.';
        } else {
            finalTips = tipsContent;
        }

        if (finalTips) {
            cardHTML += `
                <div class="tips">
                    <div class="tips-title">${t.tips}</div>
                    <div class="tips-content">${finalTips}</div>
                </div>
            `;
        }
        
        // Add full diagnostic details
        const description = lang === 'fr'
            ? result.description_fr
            : result.description_ar;

        if (description) {
            cardHTML += `
                <details class="section">
                    <summary>${lang === 'fr' ? 'Description' : 'الوصف'}</summary>
                    <p>${description}</p>
                </details>
            `;
        }

        const renderList = (titleFr, titleAr, items) => {
            if (!Array.isArray(items) || items.length === 0) return '';
            return `
                <details class="section">
                    <summary>${lang === 'fr' ? titleFr : titleAr}</summary>
                    <ul>
                        ${items.map(i => `<li>${i}</li>`).join('')}
                    </ul>
                </details>
            `;
        };

        cardHTML += renderList('Symptômes', 'الأعراض', lang === 'fr' ? result.symptoms : result.symptoms_ar);
        cardHTML += renderList('Traitement', 'العلاج', lang === 'fr' ? result.treatment : result.treatment_ar);
        cardHTML += renderList('Prévention', 'الوقاية', lang === 'fr' ? result.prevention : result.prevention_ar);
        
        card.innerHTML = cardHTML;
        resultsContainer.appendChild(card);
    });
}

// Initialize language on page load
updateLanguage();
updateStaticText(languageSelect.value);