import {
  ColumnDef,
  flexRender,
  getCoreRowModel,
  getPaginationRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { cn } from "@/lib/utils";

type Props<TData> = {
  columns: ColumnDef<TData, unknown>[];
  data: TData[];
  loading?: boolean;
  total?: number;
  page?: number;
  pageSize?: number;
  onPageChange?: (page: number) => void;
  onPageSizeChange?: (size: number) => void;
  pageSizeOptions?: number[];
  className?: string;
  emptyText?: string;
};

export default function DataTable<TData>({
  columns,
  data,
  loading,
  total,
  page = 1,
  pageSize = 50,
  onPageChange,
  onPageSizeChange,
  pageSizeOptions = [20, 50, 100],
  className,
  emptyText = "暂无数据",
}: Props<TData>) {
  const serverMode = total != null && onPageChange != null;
  const pageCount = serverMode ? Math.max(1, Math.ceil(total / pageSize)) : undefined;

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
    ...(serverMode
      ? {
          manualPagination: true,
          pageCount,
        }
      : {
          getPaginationRowModel: getPaginationRowModel(),
        }),
    state: serverMode ? { pagination: { pageIndex: page - 1, pageSize } } : undefined,
  });

  const rows = serverMode ? table.getRowModel().rows : table.getRowModel().rows;
  const displayTotal = serverMode ? total : data.length;
  const currentPage = serverMode ? page : table.getState().pagination.pageIndex + 1;
  const currentSize = serverMode ? pageSize : table.getState().pagination.pageSize;
  const totalPages = serverMode ? pageCount! : table.getPageCount();

  return (
    <div className={cn("w-full min-w-0 space-y-3", className)}>
      <div className="w-full overflow-x-auto rounded-lg border bg-card">
        <Table className="w-full table-fixed">
          <TableHeader>
            {table.getHeaderGroups().map((hg) => (
              <TableRow key={hg.id}>
                {hg.headers.map((header) => (
                  <TableHead key={header.id} style={{ width: header.getSize() !== 150 ? header.getSize() : undefined }}>
                    {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center text-muted-foreground">
                  加载中…
                </TableCell>
              </TableRow>
            ) : rows.length ? (
              rows.map((row) => (
                <TableRow key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={columns.length} className="h-24 text-center text-muted-foreground">
                  {emptyText}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
        <span>共 {displayTotal.toLocaleString()} 条</span>
        <div className="flex items-center gap-2">
          <Select
            value={String(currentSize)}
            onValueChange={(v) => {
              const n = Number(v);
              if (serverMode && onPageSizeChange) {
                onPageSizeChange(n);
                onPageChange?.(1);
              } else {
                table.setPageSize(n);
              }
            }}
          >
            <SelectTrigger className="h-8 w-[88px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {pageSizeOptions.map((n) => (
                <SelectItem key={n} value={String(n)}>
                  {n} / 页
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            size="icon"
            className="h-8 w-8"
            disabled={currentPage <= 1}
            onClick={() => (serverMode ? onPageChange?.(currentPage - 1) : table.previousPage())}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <span>
            {currentPage} / {totalPages}
          </span>
          <Button
            variant="outline"
            size="icon"
            className="h-8 w-8"
            disabled={currentPage >= totalPages}
            onClick={() => (serverMode ? onPageChange?.(currentPage + 1) : table.nextPage())}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
