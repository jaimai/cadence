import { Image as ImageIcon, Trash2, Upload, Video } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";
import { api, uploadFile } from "../api";
import { MediaThumb } from "../Composer";
import { useInvalidate, useMedia } from "../hooks";
import { Button, cx, Empty, ErrorNote, formatBytes, PageHeader, Spinner, useToast } from "../ui";

export default function MediaPage() {
  const media = useMedia();
  const invalidate = useInvalidate();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(0);
  const [dragging, setDragging] = useState(false);

  const upload = async (files: FileList | null) => {
    if (!files?.length) return;
    const list = Array.from(files);
    setUploading(list.length);
    let failed = 0;
    for (const file of list) {
      try {
        await uploadFile(file);
      } catch (e) {
        failed++;
        toast((e as Error).message, "error");
      }
      setUploading((n) => n - 1);
    }
    await invalidate("media");
    if (failed < list.length) toast(`${list.length - failed} média${list.length - failed > 1 ? "s" : ""} ajouté${list.length - failed > 1 ? "s" : ""}.`);
    if (input.current) input.current.value = "";
  };

  const remove = async (id: string) => {
    if (!window.confirm("Supprimer ce média ?")) return;
    try {
      await api.deleteMedia(id);
      await invalidate("media");
    } catch (e) {
      toast((e as Error).message, "error");
    }
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    upload(e.dataTransfer.files);
  };

  return (
    <div onDragOver={(e) => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop} className={cx("rounded-2xl", dragging && "outline-2 outline-dashed outline-brand-500 outline-offset-8")}>
      <PageHeader
        title="Médias"
        subtitle="Images JPG, PNG, WebP et vidéos MP4, MOV. Glisse tes fichiers ici."
        action={
          <>
            <input ref={input} type="file" multiple hidden accept="image/jpeg,image/png,image/webp,video/mp4,video/quicktime" onChange={(e) => upload(e.target.files)} />
            <Button variant="primary" loading={uploading > 0} onClick={() => input.current?.click()}>
              {uploading === 0 && <Upload className="size-4" />}
              {uploading > 0 ? `Envoi en cours (${uploading})` : "Importer"}
            </Button>
          </>
        }
      />
      {media.isError && <ErrorNote>{media.error.message}</ErrorNote>}
      {media.isPending ? (
        <Spinner />
      ) : media.data?.length === 0 ? (
        <Empty icon={<ImageIcon className="size-5" />} title="Ta médiathèque est vide">
          Importe des images ou des vidéos pour les utiliser dans tes posts.
        </Empty>
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {media.data?.map((m) => (
            <figure key={m.id} className="group relative overflow-hidden rounded-xl bg-white ring-1 ring-slate-200">
              <div className="relative aspect-square bg-slate-100">
                <MediaThumb media={m} />
                {m.kind === "video" && <Video className="absolute left-2 top-2 size-5 rounded bg-slate-900/60 p-0.5 text-white" />}
                <button
                  aria-label={`Supprimer ${m.filename}`}
                  onClick={() => remove(m.id)}
                  className="absolute right-2 top-2 rounded-lg bg-white/90 p-1.5 text-red-600 opacity-0 shadow hover:bg-white focus:opacity-100 group-hover:opacity-100"
                >
                  <Trash2 className="size-4" />
                </button>
              </div>
              <figcaption className="px-3 py-2">
                <p className="truncate text-sm" title={m.filename}>{m.filename}</p>
                <p className="text-xs text-slate-400">{formatBytes(m.size)}</p>
              </figcaption>
            </figure>
          ))}
        </div>
      )}
    </div>
  );
}
