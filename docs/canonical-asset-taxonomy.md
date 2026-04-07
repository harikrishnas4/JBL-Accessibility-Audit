# Canonical Asset Taxonomy

The canonical asset taxonomy is defined in [packages/contracts/asset-taxonomy.json](/C:/Users/harikrishnam/Desktop/JBL%20accessibilty/packages/contracts/asset-taxonomy.json).

Current crawler legacy-to-canonical mappings:

| Legacy crawler output | Canonical asset type | Why |
| --- | --- | --- |
| `course_page` | `web_page` | `mod/page` is a first-party course page and should be audited as a web page. |
| `course_quiz` | `quiz_page` | `mod/quiz` is a quiz interaction surface. |
| `course_lti` | `lti_launch` | `mod/lti` is the launch surface into an external tool. |
| `course_link` | `web_page` | `mod/url` is the course-owned launch page. The destination resource is classified separately when discovered as a PDF, media file, or embed. |

Additional crawler normalization rules:

| Observed resource | Canonical asset type | Notes |
| --- | --- | --- |
| PDF links | `document_pdf` | Applies before host-specific rules. |
| JBL CDN timed media | `media_video` | Used for timed-media extensions such as `.mp4`, `.mov`, and `.webm`. |
| JBL CDN script/embed bundles | `component` | Used for first-party embedded player bundles and non-document embed resources. |
| BioDigital embeds | `third_party_embed` | Preserves third-party routing. |
| Unsupported external embeds | `third_party_embed` | Must remain explicit `out_of_scope` assets with a reason. |
| Unsupported Moodle module pages | `web_page` | Must remain explicit `out_of_scope` assets with a reason. |
