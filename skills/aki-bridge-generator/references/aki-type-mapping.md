# AKI 类型映射参考

## 基本类型映射

| C++ 类型 | ArkTS 类型 | 方向 | 说明 |
|----------|-----------|------|------|
| `bool` | `boolean` | 双向 | 直接映射 |
| `int` / `int32_t` | `number` | 双向 | 32位整数 |
| `int64_t` | `number` | 双向 | 64位整数（注意精度） |
| `float` | `number` | 双向 | 单精度浮点 |
| `double` | `number` | 双向 | 双精度浮点 |
| `std::string` | `string` | 双向 | UTF-8 编码自动转换 |
| `const char*` | `string` | C++→ArkTS | 仅输出方向 |
| `void` | `void` | — | 无返回值 |

## 容器类型映射

| C++ 类型 | ArkTS 类型 | 方向 | 说明 |
|----------|-----------|------|------|
| `std::vector<int>` | `number[]` | 双向 | 整数数组 |
| `std::vector<std::string>` | `string[]` | 双向 | 字符串数组 |
| `std::vector<double>` | `number[]` | 双向 | 浮点数组 |
| `std::map<std::string, std::string>` | `Record<string, string>` | 双向 | 键值映射 |
| `std::unordered_map<K, V>` | `Record<K, V>` | 双向 | 无序映射 |

## 回调函数映射

| C++ 类型 | ArkTS 类型 | 方向 | 说明 |
|----------|-----------|------|------|
| `std::function<void()>` | `() => void` | C++→ArkTS | 无参数回调 |
| `std::function<void(int)>` | `(code: number) => void` | C++→ArkTS | 单参数回调 |
| `std::function<void(int, std::string)>` | `(code: number, msg: string) => void` | C++→ArkTS | 多参数回调 |
| `std::function<void(bool)>` | `(result: boolean) => void` | C++→ArkTS | 布尔回调 |
| `std::function<int(std::string)>` | `(msg: string) => number` | 双向 | 有返回值回调 |

## 自定义类映射

| C++ 类型 | ArkTS 类型 | 条件 | 说明 |
|----------|-----------|------|------|
| 自定义 C++ class | ArkTS class | 需要 `JSBIND_CLASS` 注册 | 对象映射 |
| 自定义 C++ class* | ArkTS class | 需要 `JSBIND_CLASS` + 引用计数 | 指针映射 |

### 自定义类映射示例

```cpp
// C++ 侧
class FileInfo {
public:
    std::string fileName;
    std::string filePath;
    int fileSize;
};

JSBIND_CLASS(FileInfo) {
    JSBIND_PROPERTY(fileName);
    JSBIND_PROPERTY(filePath);
    JSBIND_PROPERTY(fileSize);
}
```

ArkTS 侧：
```typescript
class FileInfo {
    fileName: string;
    filePath: string;
    fileSize: number;
}
```

## 不支持的类型

以下 C++ 类型**不能直接**用于 AKI 桥接：

| 不支持的类型 | 替代方案 |
|-------------|---------|
| `QByteArray` | 转换为 `std::string` 后桥接 |
| `QString` | 转换为 `std::string` 后桥接（`QString::toStdString()`） |
| `QStringList` | 转换为 `std::vector<std::string>` 后桥接 |
| `QVariant` | 转换为 `std::string`（JSON）后桥接 |
| `QMap<QString, T>` | 转换为 `std::map<std::string, T>` 后桥接 |
| `QList<T>` | 转换为 `std::vector<T>` 后桥接 |
| `QJsonObject` | 转换为 `std::string`（JSON）后桥接 |
| `QImage` / `QPixmap` | 转换为 `std::string`（Base64编码）后桥接 |
| 原始指针 `T*`（非 AKI 注册类） | 使用 `std::shared_ptr<T>` 或值传递 |
| C 函数指针 `void(*)(...)` | 使用 `std::function<void(...)>` 替代 |

## Qt 类型转换辅助函数

在桥接代码中，常用 Qt 类型到 AKI 支持类型的转换：

```cpp
// QString → std::string
std::string qtStringToStd(const QString& qstr) {
    return qstr.toStdString();
}

// std::string → QString
QString stdToQtString(const std::string& str) {
    return QString::fromStdString(str);
}

// QByteArray → std::string (Base64)
std::string qtByteArrayToBase64(const QByteArray& data) {
    return data.toBase64().toStdString();
}

// QImage → std::string (Base64 PNG)
std::string qtImageToBase64(const QImage& image) {
    QByteArray ba;
    QBuffer buffer(&ba);
    buffer.open(QIODevice::WriteOnly);
    image.save(&buffer, "PNG");
    return ba.toBase64().toStdString();
}

// QStringList → std::vector<std::string>
std::vector<std::string> qtStringListToStdVec(const QStringList& list) {
    std::vector<std::string> result;
    for (const QString& item : list) {
        result.push_back(item.toStdString());
    }
    return result;
}
```

## 注意事项

1. **所有 Qt 特有类型必须先转换为 AKI 支持类型**：这是 Qt + AKI 桥接的核心原则
2. **大文件/大数据传递建议使用 Base64 或文件路径**：避免桥接层传输过多数据
3. **64位整数注意精度**：JavaScript number 类型在超过 2^53 时会丢失精度
4. **回调函数参数类型必须严格匹配**：两端签名不一致会导致运行时错误