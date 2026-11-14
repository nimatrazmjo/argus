{{/*
Image ref. Default: upstream ref as-is. If .Values.imageRegistry is set,
rewrite to <registry>/argus/<basename:tag> (matches deploy/images.txt ACR import).
Usage: {{ include "argus.image" (list $ "repo/name:tag") }}
*/}}
{{- define "argus.image" -}}
{{- $root := index . 0 -}}
{{- $ref := index . 1 -}}
{{- if $root.Values.imageRegistry -}}
{{- printf "%s/argus/%s" (trimSuffix "/" $root.Values.imageRegistry) (base $ref) -}}
{{- else -}}
{{- $ref -}}
{{- end -}}
{{- end -}}

{{/*
Common labels
*/}}
{{- define "argus.labels" -}}
app.kubernetes.io/part-of: argus
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}
