{{/*
Expand image reference: registry/argus/<name>
*/}}
{{- define "argus.image" -}}
{{- printf "%s/argus/%s" .Values.imageRegistry . -}}
{{- end -}}

{{/*
Common labels
*/}}
{{- define "argus.labels" -}}
app.kubernetes.io/part-of: argus
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}
